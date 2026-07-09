import mt5_worker as mt5
import asyncio
import time as _time
from datetime import datetime
from bot_log import log_event, log_error, setup_python_logging, cleanup_old_logs
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.error import Conflict, NetworkError
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import *
import config
from config import wrap_bot
from scanner import auto_scan
from trailing import (check_entry_candle_quality, check_engulf_trail_sl,
                      check_breakeven_tp, check_opposite_order_tp,
                      check_cancel_pending_orders, check_s1_zone_rules, check_s1_forward_confirm_rules, check_s6_trail,
                      check_limit_sweep, check_scale_out_partial, check_fill_rsi_recheck, check_limit_fill_notify,
                      check_fill_trend_recheck, check_pending_trend_approach, check_fill_pdfiboplus,
                      check_s14_engulf_exits, check_s20_escape, check_s2_s3_chain_groups,
                      check_s1_rejection_entry)
from notifications import check_sl_tp_hits
from handlers.text_handler import start, handle_text
from handlers.callback_handler import handle_callback

_error_last_sent: dict = {}
_ERROR_COOLDOWN = 300  # วินาที — ไม่ส่ง error ซ้ำภายใน 5 นาที


def _install_stall_watchdog() -> None:
    """ติดตั้ง diagnostic watchdog สำหรับ STALL — ถ้า event loop แข็ง (MT5 call
    ค้าง) นานเกิน config.STALL_TRACE_TIMEOUT วิ จะ dump stack trace ของทุก
    thread ไปไฟล์ logs/debug/stall_trace.log ให้รู้ว่าค้างอยู่ที่บรรทัด/MT5
    call ไหนแน่ ๆ (ก่อนหน้านี้ supervisor kill ที่ 180s ก่อน log ไหนจะทันเขียน)

    ใช้ watchdog thread ภายในของ faulthandler เอง (อ่าน stack อย่างเดียว ไม่เรียก
    MT5 เลย) — ไม่ย้าย MT5 call ไป thread อื่นเด็ดขาด (เคยทำพัง order_send มาแล้ว
    เพราะ MT5 ผูกกับ thread ที่ initialize ไว้)
    """
    import faulthandler
    from bot_log import DEBUG_LOG_DIR
    import os as _os
    _os.makedirs(DEBUG_LOG_DIR, exist_ok=True)
    path = _os.path.join(DEBUG_LOG_DIR, "stall_trace.log")
    f = open(path, "a", encoding="utf-8")
    config._stall_trace_file = f
    faulthandler.enable(file=f)
    _rearm_stall_watchdog()


def _rearm_stall_watchdog() -> None:
    """รีเซ็ตนาฬิกาจับเวลา — เรียกทุกครั้งที่ event loop ยังมีชีวิต (จาก
    write_heartbeat_job ทุก 15s) ถ้า loop แข็งจริง จะไม่มีใครมาเรียกฟังก์ชันนี้
    ต่อ → ตัวจับเวลาที่ตั้งไว้ครั้งล่าสุดจะ fire เอง แล้ว dump stack"""
    import faulthandler
    if config._stall_trace_file is None:
        return
    faulthandler.cancel_dump_traceback_later()
    faulthandler.dump_traceback_later(
        config.STALL_TRACE_TIMEOUT, repeat=False,
        file=config._stall_trace_file, exit=False,
    )


async def _tg_error(app, job_name: str, exc: Exception) -> None:
    """ส่ง error ไป Telegram พร้อม dedup กัน spam"""
    import time, traceback
    key = f"{job_name}:{type(exc).__name__}:{str(exc)[:80]}"
    now = time.time()
    if now - _error_last_sent.get(key, 0) < _ERROR_COOLDOWN:
        return
    _error_last_sent[key] = now
    tb = traceback.format_exc()
    short_tb = tb[-500:] if len(tb) > 500 else tb
    msg = (
        f"🚨 *Bot Error — {job_name}*\n"
        f"`{type(exc).__name__}: {str(exc)[:200]}`\n"
        f"```\n{short_tb}\n```"
    )
    log_event("BOT_ERROR", f"{job_name} error: {type(exc).__name__}: {exc}")
    log_error("BOT_ERROR", f"{job_name} | {type(exc).__name__}: {exc}\n{short_tb}")
    try:
        await app.bot.send_message(chat_id=MY_USER_ID, text=msg, parse_mode="Markdown")
    except Exception:
        pass


async def _handle_app_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Central handler for telegram.ext callback and polling errors."""
    import traceback

    exc = context.error
    if isinstance(exc, NetworkError):
        log_event("TG_NETWORK_ERROR", str(exc)[:200])
        return
    if isinstance(exc, Conflict):
        log_event("TG_WEBHOOK_CONFLICT", str(exc)[:200])
        try:
            await context.bot.delete_webhook(drop_pending_updates=True)
            log_event("TG_WEBHOOK_CONFLICT", "delete_webhook ok")
        except Exception as delete_exc:
            log_error(
                "TG_WEBHOOK_DELETE_ERROR",
                f"{type(delete_exc).__name__}: {delete_exc}",
            )
        return

    tb = "".join(traceback.format_exception(None, exc, exc.__traceback__)) if exc else ""
    log_error(
        "TG_APP_ERROR",
        f"{type(exc).__name__ if exc else 'UnknownError'}: {exc}\n{tb[-800:]}",
    )


def main():
    import sys as _sys, traceback as _tb2

    def _fatal_excepthook(exc_type, exc_value, exc_tb):
        """จับ exception ที่หลุดออกมาโดยไม่มี try/except — เขียนลง error log"""
        if issubclass(exc_type, KeyboardInterrupt):
            _sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        tb_str = "".join(_tb2.format_exception(exc_type, exc_value, exc_tb))
        try:
            log_error("FATAL_ERROR", f"{exc_type.__name__}: {exc_value}\n{tb_str[-800:]}")
        except Exception:
            pass
        _sys.__excepthook__(exc_type, exc_value, exc_tb)

    _sys.excepthook = _fatal_excepthook

    setup_python_logging()
    mt5.start_worker()
    _install_stall_watchdog()
    log_event("APP_START", "Bot starting", symbol=SYMBOL, scan_interval=SCAN_INTERVAL)
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🤖 Copter Gold Bot — ท่าที่ 1")
    print("📊 A: กลืนกิน (เขียว/แดง 2 แท่ง)")
    print("📊 B: ตำหนิ+Confirm (เขียว/แดง 2 แท่ง)")
    print(f"⏰ สแกนทุก {SCAN_INTERVAL} นาที | TF: {[tf for tf,on in TF_ACTIVE.items() if on]}")
    print("⚠️ ต้องเปิด MT5 ทิ้งไว้ตลอด!")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(_handle_app_error)

    scheduler = AsyncIOScheduler()

    async def run_scan():
        try:
            import news_filter
            import config
            import time as _time
            from mt5_utils import connect_mt5

            is_active, reason = news_filter.is_news_embargo_active()
            
            if is_active:
                observable = getattr(config, "OBSERVABLE_MODE", False)
                if not getattr(config, "news_pause_active", False):
                    config.news_pause_active = True
                    if observable:
                        await tg(app, f"👀 *[OBSERVABLE] News Embargo Active*\n{reason}\n(โหมดสังเกตการณ์: ไม่ได้ระงับจริง)")
                        print(f"[{now_bkk().strftime('%H:%M:%S')}] 👀 [OBSERVABLE] News Embargo Active: {reason} - Would have canceled orders.")
                    else:
                        await tg(app, f"⚠️ *News Embargo Active*\n{reason}\n⛔ ระงับการเปิดไม้ใหม่และยกเลิก Pending")
                        print(f"[{now_bkk().strftime('%H:%M:%S')}] 📰 News Embargo Active: {reason}")
                        
                        if connect_mt5():
                            import mt5_worker as mt5
                            from trailing import pending_order_tf
                            orders = mt5.orders_get(symbol=config.SYMBOL)
                            if orders:
                                canceled_count = 0
                                skip_sids = getattr(config, "NEWS_FILTER_SKIP_SIDS", set())
                                for o in orders:
                                    sid = pending_order_tf.get(o.ticket, {}).get("sid")
                                    if sid in skip_sids:
                                        continue
                                    req = {"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket}
                                    mt5.order_send(req)
                                    canceled_count += 1
                                if canceled_count > 0:
                                    print(f"[{now_bkk().strftime('%H:%M:%S')}] 📰 Canceled {canceled_count} pending orders due to news.")
                
                # Removed short-circuit return to allow bypassed strategies to run
                
            if getattr(config, "news_pause_active", False) and not is_active:
                config.news_pause_active = False
                observable = getattr(config, "OBSERVABLE_MODE", False)
                if observable:
                    await tg(app, "👀 *[OBSERVABLE] News Embargo Lifted*")
                    print(f"[{now_bkk().strftime('%H:%M:%S')}] 👀 [OBSERVABLE] News Embargo Lifted")
                else:
                    await tg(app, "✅ *News Embargo Lifted*\nบอทกลับมาสแกนตามปกติ")
                    print(f"[{now_bkk().strftime('%H:%M:%S')}] 📰 News Embargo Lifted")

            await auto_scan(app)
            config.last_scan_ts = _time.time()   # heartbeat สำหรับ watchdog
        except Exception as e:
            await _tg_error(app, "run_scan", e)

    async def run_demo_portfolio_scan():
        """P13 (Champion) / P16 (Max-Yield Blend) — ระบบทดสอบแยกอิสระจากบอทหลัก
        (ดู demo_portfolio.py) ไม่แตะ active_strategies/scanner.py/trailing.py state ใดๆ
        no-op ถ้าไม่มี portfolio ไหน active (default ปิดทั้งคู่)"""
        try:
            import demo_portfolio
            await demo_portfolio.demo_scan_job(app)
        except Exception as e:
            await _tg_error(app, "run_demo_portfolio_scan", e)

    async def _close_btc_exposure_before_xau_switch():
        """ปิด position และลบ pending ของ BTCUSD ก่อนสลับกลับ XAUUSD"""
        btc_symbol = config.resolve_mt5_symbol(mt5, "BTCUSD", set_runtime=False)
        closed_positions = []
        canceled_orders = []

        try:
            from trailing import pending_order_tf, position_tf, position_sid, position_pattern, position_zone_meta, _entry_state
        except Exception:
            pending_order_tf = {}
            position_tf = {}
            position_sid = {}
            position_pattern = {}
            position_zone_meta = {}
            _entry_state = {}

        btc_orders = mt5.orders_get(symbol=btc_symbol) or []
        for o in btc_orders:
            r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                ticket = int(o.ticket)
                canceled_orders.append(ticket)
                pending_order_tf.pop(ticket, None)
                position_tf.pop(ticket, None)
                position_sid.pop(ticket, None)
                position_pattern.pop(ticket, None)
                position_zone_meta.pop(ticket, None)
                _entry_state.pop(ticket, None)
                log_event("ORDER_CANCELED", "BTC pending cleared before switching to XAUUSD", symbol=btc_symbol, ticket=ticket)

        btc_positions = mt5.positions_get(symbol=btc_symbol) or []
        for pos in btc_positions:
            tick = mt5.symbol_info_tick(btc_symbol)
            if not tick:
                continue
            is_buy = pos.type == mt5.ORDER_TYPE_BUY
            close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
            close_price = float(tick.bid if is_buy else tick.ask)
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": btc_symbol,
                "position": pos.ticket,
                "volume": pos.volume,
                "type": close_type,
                "price": close_price,
                "deviation": 20,
                "magic": int(getattr(config, "MAGIC_NUMBER", 234001) or 234001),
                "comment": "switch_to_xau_close_btc",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            r = mt5.order_send(req)
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                ticket = int(pos.ticket)
                closed_positions.append(ticket)
                pending_order_tf.pop(ticket, None)
                position_tf.pop(ticket, None)
                position_sid.pop(ticket, None)
                position_pattern.pop(ticket, None)
                position_zone_meta.pop(ticket, None)
                _entry_state.pop(ticket, None)
                log_event(
                    "POSITION_CLOSED",
                    "BTC position closed before switching to XAUUSD",
                    symbol=btc_symbol,
                    ticket=ticket,
                    close_price=close_price,
                )

        if closed_positions or canceled_orders:
            lines = ["🧹 *ล้าง BTCUSD ก่อนสลับกลับ XAUUSD*"]
            if closed_positions:
                lines.append(f"📉 ปิด position BTC: `{', '.join(map(str, closed_positions))}`")
            if canceled_orders:
                lines.append(f"🗑️ ลบ pending BTC: `{', '.join(map(str, canceled_orders))}`")
            await tg(app, "\n".join(lines))
            print(
                f"[{now_bkk().strftime('%H:%M:%S')}] 🧹 cleared BTC before switch "
                f"positions={closed_positions} pending={canceled_orders}"
            )
        return bool(closed_positions or canceled_orders)

    async def check_symbol_switch(startup: bool = False):
        """ตรวจตลาด XAUUSD — ถ้าปิดสลับไป BTCUSD ถ้าเปิดสลับกลับ
        startup=True → บังคับ set_runtime_symbol ทุกครั้งเพื่ออัปเดต module และ TG startup message
        """
        import config
        from mt5_utils import connect_mt5
        if not connect_mt5():
            return
        try:
            xau_symbol = config.resolve_mt5_symbol(mt5, "XAUUSD", set_runtime=False)
            btc_symbol = config.resolve_mt5_symbol(mt5, "BTCUSD", set_runtime=False)
            xau_info = mt5.symbol_info(xau_symbol)
            if xau_info is None:
                return
            xau_tick = mt5.symbol_info_tick(xau_symbol)
            now_ts = int(datetime.now().timestamp())
            tick_ok = (
                xau_tick is not None
                and getattr(xau_tick, "time", 0) > 0
                and (now_ts - int(getattr(xau_tick, "time", 0))) <= 180
                and (float(getattr(xau_tick, "bid", 0.0)) > 0 or float(getattr(xau_tick, "ask", 0.0)) > 0)
            )
            xau_open = (xau_info.trade_mode != 0) and tick_ok
            print(
                f"[{now_bkk().strftime('%H:%M:%S')}] 🔎 symbol_check {xau_symbol} "
                f"trade_mode={xau_info.trade_mode} "
                f"tick_time={getattr(xau_tick, 'time', 0)} "
                f"bid={getattr(xau_tick, 'bid', 0.0)} ask={getattr(xau_tick, 'ask', 0.0)} "
                f"tick_ok={tick_ok} => xau_open={xau_open}"
            )
            log_event(
                "SYMBOL_CHECK",
                f"{xau_symbol} trade_mode={xau_info.trade_mode} xau_open={xau_open}",
                trade_mode=xau_info.trade_mode,
                tick_time=getattr(xau_tick, "time", 0),
                bid=float(getattr(xau_tick, "bid", 0.0)),
                ask=float(getattr(xau_tick, "ask", 0.0)),
                tick_ok=tick_ok,
                xau_open=xau_open,
                current_symbol=config.SYMBOL,
                startup=startup,
            )
        except Exception as e:
            print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ check_symbol_switch error: {e}")
            log_error("SYMBOL_SWITCH_ERROR", f"{type(e).__name__}: {e}")
            return
        if xau_open:
            if config._symbol_root(config.SYMBOL).startswith("BTCUSD") or config.SYMBOL != xau_symbol:
                # กัน scan สร้างออเดอร์ระหว่างปิด BTC + สลับ symbol (race guard)
                config.symbol_switch_in_progress = True
                try:
                    if config._symbol_root(config.SYMBOL).startswith("BTCUSD"):
                        await _close_btc_exposure_before_xau_switch()
                    set_runtime_symbol(xau_symbol)
                    save_runtime_state()
                finally:
                    config.symbol_switch_in_progress = False
                await tg(app, f"🟡 *XAUUSD เปิดแล้ว* → สลับกลับ {xau_symbol}")
                print(f"[{now_bkk().strftime('%H:%M:%S')}] 🔄 สลับกลับ {xau_symbol}")
                if config.auto_active:
                    await tg(app, f"⚡ *สั่งสแกนทันทีหลังสลับ symbol* \n📈 SYMBOL: `{xau_symbol}`")
                    print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚡ trigger immediate scan after symbol switch -> {xau_symbol}")
                    await auto_scan(app)
            elif startup:
                # ตอน start: SYMBOL เป็น XAUUSD อยู่แล้ว → force setattr ให้ทุก module + ไม่ส่ง TG ซ้ำ
                set_runtime_symbol(xau_symbol)
                print(f"[{now_bkk().strftime('%H:%M:%S')}] ✅ startup: {xau_symbol} เปิดอยู่ (ไม่ต้องสลับ)")
        elif not xau_open and (config._symbol_root(config.SYMBOL).startswith("XAUUSD") or config.SYMBOL != btc_symbol):
            # กัน scan สร้างออเดอร์ระหว่างสลับ symbol (race guard)
            config.symbol_switch_in_progress = True
            try:
                set_runtime_symbol(btc_symbol)
                save_runtime_state()
            finally:
                config.symbol_switch_in_progress = False
            await tg(app, f"🔵 *XAUUSD ปิด* → สลับไป {btc_symbol}")
            print(f"[{now_bkk().strftime('%H:%M:%S')}] 🔄 สลับไป {btc_symbol}")
            if config.auto_active:
                await tg(app, f"⚡ *สั่งสแกนทันทีหลังสลับ symbol* \n📈 SYMBOL: `{btc_symbol}`")
                print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚡ trigger immediate scan after symbol switch -> {btc_symbol}")
                await auto_scan(app)

    async def run_trail_sl():
        """Trail SL — รันได้เลย ไม่ต้องรอ
        มี timing breakdown กัน MT5 call ค้างแบบไม่รู้ตัว (เหมือน auto_scan ใน scanner.py)"""
        if not config.auto_active:
            return
        from mt5_utils import connect_mt5
        if not connect_mt5():
            return
        _steps: list[tuple[str, float]] = []
        _t0 = _time.perf_counter()

        def _lap(label: str) -> None:
            _steps.append((label, _time.perf_counter() - _t0))

        try:
            await check_engulf_trail_sl(app); _lap("engulf_trail_sl")
            await check_s6_trail(app); _lap("s6_trail")
        except Exception as e:
            await _tg_error(app, "run_trail_sl", e)
        finally:
            _total = _steps[-1][1] if _steps else (_time.perf_counter() - _t0)
            if _total > 3.0:
                _prev = 0.0
                _breakdown = []
                for _label, _t in _steps:
                    _breakdown.append(f"{_label}={_t - _prev:.2f}s")
                    _prev = _t
                log_event("TRAIL_SL_SLOW", f"run_trail_sl ใช้เวลา {_total:.2f}s > 3s",
                          breakdown=" ".join(_breakdown))

    async def run_position_check():
        """Position management — รอ job ก่อนหน้าเสร็จก่อน (กัน race condition)
        มี timing breakdown กัน MT5 call ค้างแบบไม่รู้ตัว (เหมือน auto_scan ใน scanner.py)"""
        if not config.auto_active:
            return
        from mt5_utils import connect_mt5
        if not connect_mt5():
            return
        _steps: list[tuple[str, float]] = []
        _t0 = _time.perf_counter()

        def _lap(label: str) -> None:
            _steps.append((label, _time.perf_counter() - _t0))

        try:
            # Limit Fill notify ก่อน (อิสระจาก ENTRY_CANDLE_ENABLED)
            await check_limit_fill_notify(app); _lap("limit_fill_notify")
            
            # LTS Exit Manager (Phase 4 isolation)
            from demo_portfolio import lts_exit_manager
            await lts_exit_manager(app); _lap("lts_exit_manager")

            # RSI Fill Recheck รันก่อน entry candle — ถ้า fail ปิด position ทันที
            await check_fill_rsi_recheck(app); _lap("fill_rsi_recheck")
            # Pending Trend Check on Approach — เช็ค trend ของ pending ก่อน fill (200pt)
            await check_pending_trend_approach(app); _lap("pending_trend_approach")
            # Trend Fill Recheck — เช็ค trend หลัง fill (round1 + round2/3 หลัง H/L เปลี่ยน)
            await check_fill_trend_recheck(app); _lap("fill_trend_recheck")
            # PD Fibo Plus Fill Check — อิสระจาก ENTRY_CANDLE_ENABLED จับ case fill เร็วกว่า pending cycle
            await check_fill_pdfiboplus(app); _lap("fill_pdfiboplus")
            await check_s14_engulf_exits(app); _lap("s14_engulf_exits")
            await check_s20_escape(app); _lap("s20_escape")
            await check_entry_candle_quality(app); _lap("entry_candle_quality")
            await check_sl_tp_hits(app); _lap("sl_tp_hits")
            await check_s1_zone_rules(app); _lap("s1_zone_rules")
            await check_s1_rejection_entry(app); _lap("s1_rejection_entry")
            await check_s2_s3_chain_groups(app); _lap("s2_s3_chain_groups")
            # Disabled per user request (2026-06-29): keep S1 pending/position
            # even when no same-side S2/S3 appears within the forward window.
            # await check_s1_forward_confirm_rules(app); _lap("s1_forward_confirm_rules")
            await check_cancel_pending_orders(app); _lap("cancel_pending_orders")
            # await check_breakeven_tp(app)  # ปิดชั่วคราว
            await check_opposite_order_tp(app); _lap("opposite_order_tp")
            await check_limit_sweep(app); _lap("limit_sweep")
            await check_scale_out_partial(app); _lap("scale_out_partial")
        except Exception as e:
            await _tg_error(app, "run_position_check", e)
        finally:
            _total = _steps[-1][1] if _steps else (_time.perf_counter() - _t0)
            if _total > 3.0:
                _prev = 0.0
                _breakdown = []
                for _label, _t in _steps:
                    _breakdown.append(f"{_label}={_t - _prev:.2f}s")
                    _prev = _t
                log_event("POSITION_CHECK_SLOW", f"run_position_check ใช้เวลา {_total:.2f}s > 3s",
                          breakdown=" ".join(_breakdown))

    async def save_bot_state_job():
        """บันทึก state สำคัญเป็นระยะ เพื่อลดปัญหา pattern/state หายหลัง restart"""
        save_runtime_state()

    async def cleanup_logs_job():
        """ลบ log ที่เก่าเกิน 7 วัน — รันเที่ยงคืน BKK"""
        summary = cleanup_old_logs()
        log_event(
            "LOG_CLEANUP",
            "ลบ log เก่าเกิน 7 วัน",
            trimmed=len(summary.get("trimmed") or []),
            deleted=len(summary.get("deleted") or []),
            skipped=len(summary.get("skipped") or []),
        )

    async def daily_summary_job():
        """ส่งสรุปผลประจำวันไป Telegram ตามเวลา BKK (DAILY_SUMMARY_HOUR:MINUTE)"""
        if not config.DAILY_SUMMARY_ENABLED:
            return
        try:
            from mt5_utils import connect_mt5
            connect_mt5()
            text = config.build_daily_summary_text()
            await tg(app, text)
            log_event("DAILY_SUMMARY", "sent",
                      realized=config.daily_stats.get("realized", 0.0),
                      count=config.daily_stats.get("count", 0))
        except Exception as e:
            await _tg_error(app, "daily_summary_job", e)

    async def run_watchdog():
        """Health check เบาๆ ทุก 1 นาที — เขียน heartbeat + เช็ก MT5/scan ค้าง
        แจ้ง Telegram เมื่อผิดปกติและเมื่อกลับมาปกติ (กันแจ้งซ้ำด้วย flag ใน config)"""
        if not config.WATCHDOG_ENABLED:
            return
        from mt5_utils import connect_mt5
        mt5_ok = False
        try:
            mt5_ok = bool(connect_mt5())
        except Exception:
            mt5_ok = False

        # heartbeat file (ให้ external supervisor เช็กได้ว่า process ยังมีชีวิต)
        # เขียนพร้อม mt5_ok สด — ส่วน heartbeat_job (15s) เขียน stamp ถี่กว่าด้วยค่า cached
        config.write_heartbeat(mt5_ok=mt5_ok)

        # MT5 connection transition alerts
        if not mt5_ok and config._watchdog_mt5_ok:
            config._watchdog_mt5_ok = False
            log_event("WATCHDOG_MT5_DOWN", "MT5 connection lost")
            await tg(app, "🚨 *Watchdog: MT5 หลุดการเชื่อมต่อ*\nบอทจะลองเชื่อมต่อใหม่อัตโนมัติ")
        elif mt5_ok and not config._watchdog_mt5_ok:
            config._watchdog_mt5_ok = True
            log_event("WATCHDOG_MT5_UP", "MT5 connection restored")
            await tg(app, "✅ *Watchdog: MT5 กลับมาเชื่อมต่อแล้ว*")

        # scan stall alert (เฉพาะตอน auto ON และเคย scan มาแล้ว)
        if config.auto_active and config.last_scan_ts > 0:
            stale = (_time.time() - config.last_scan_ts) > config.WATCHDOG_STALE_SEC
            if stale and config._watchdog_scan_ok:
                config._watchdog_scan_ok = False
                gap = int(_time.time() - config.last_scan_ts)
                log_event("WATCHDOG_SCAN_STALL", f"no scan for {gap}s")
                await tg(app, f"🚨 *Watchdog: Scan ค้าง*\nไม่มี scan สำเร็จมา `{gap}` วินาที — ตรวจสอบ MT5/บอท")
            elif not stale and not config._watchdog_scan_ok:
                config._watchdog_scan_ok = True
                log_event("WATCHDOG_SCAN_OK", "scan resumed")
                await tg(app, "✅ *Watchdog: Scan กลับมาทำงานปกติ*")

    async def write_heartbeat_job():
        """เขียน heartbeat ถี่ (ทุก 15s) ให้ external supervisor detect loop hang ได้ไว
        ไม่เรียก MT5 — แค่ stamp ts; ถ้า event loop แข็ง (mt5 blocking call ค้าง)
        ts จะ freeze ทันที → supervisor เห็น ts เก่าเกิน threshold → kill+restart"""
        config.write_heartbeat()
        _rearm_stall_watchdog()
        await _check_mt5_wedge(app)

    async def _check_mt5_wedge(app, stale_after: float = 60.0) -> None:
        """ตรวจว่า mt5_worker thread ค้างอยู่กลาง call นานเกิน stale_after วิหรือไม่
        (อ่านแค่ตัวแปร in-memory ของ mt5_worker — ไม่เรียก MT5 เอง จึงไม่ค้างตามไปด้วย)
        ถ้าค้างจริง → log + แจ้ง Telegram (event loop ไม่ถูกบล็อกแล้ว จึงส่งได้) แล้ว
        os._exit(1) ให้ supervisor restart ทันที เร็วกว่ารอ heartbeat-stale kill"""
        if not mt5.is_wedged(stale_after):
            return
        info = mt5.wedge_info()
        log_event("MT5_WORKER_WEDGED", f"mt5_worker thread ค้าง: {info}")
        try:
            await tg(app, f"🚨 *MT5 Worker ค้าง*\n`{info}`\nกำลัง restart บอท...")
        except Exception:
            pass
        import os as _os
        _os._exit(1)

    from datetime import timezone as _tz2

    # ตรวจสลับ symbol ทุก 1 นาที
    scheduler.add_job(
        check_symbol_switch,
        'interval',
        minutes=1,
        id="symbol_switch_job",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(_tz2.utc)
    )

    # Pattern scan ทุก 5 วินาที — max_instances=1 กัน scan วิ่งซ้อน
    # (race: _scan_results.clear ทับกัน + ออเดอร์ซ้ำเพราะ dedup อยู่นอก lock)
    # coalesce=True → ถ้ารอบก่อนยังไม่จบ ให้รวบรอบที่ค้างเป็นรอบเดียว
    # ใช้ CronTrigger ยึดกับวินาทีนาฬิกาจริง (:01,:06,:11,...,:56) แทน interval เดิมที่จังหวะ
    # ลอยตามวินาทีที่ bot start ทำให้ scan อาจตามหลังแท่งที่เพิ่งปิดได้นานสุดถึง ~5 วิ
    # แบบสุ่ม — CronTrigger รับประกันว่ามี scan ที่วินาทีที่ 1 ของทุกนาทีเสมอ (market order
    # ของ sid ที่ order_mode=market เช่น S20.12/S14 จะยิงไม่เกินวิ 1-3 หลังแท่งปิดจริง)
    scheduler.add_job(
        run_scan,
        CronTrigger(second="1,6,11,16,21,26,31,36,41,46,51,56"),
        id="auto_scan_job",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=5
    )

    # Demo Portfolio (P13/P16) — สแกนแยกอิสระจากบอทหลัก ทุก DEMO_PORTFOLIO_SCAN_INTERVAL นาที
    # (no-op ถ้าไม่มี portfolio ไหน active — ดู config.DEMO_PORTFOLIO_ACTIVE)
    scheduler.add_job(
        run_demo_portfolio_scan,
        'interval',
        minutes=config.DEMO_PORTFOLIO_SCAN_INTERVAL,
        id="demo_portfolio_scan_job",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(_tz2.utc)
    )

    # Trail SL ทุก 5 วินาที — max_instances=1 กันแก้ SL ของ position เดียวซ้อนกัน
    from datetime import timezone as _tz
    scheduler.add_job(
        run_trail_sl,
        'interval',
        seconds=5,
        id="trail_sl_job",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=10,
        next_run_time=datetime.now(_tz.utc)
    )

    # Position check ทุก 5 วินาที — รอ job ก่อนหน้าเสร็จ
    scheduler.add_job(
        run_position_check,
        'interval',
        seconds=5,
        id="position_check_job",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(_tz.utc)
    )

    scheduler.add_job(
        save_bot_state_job,
        'interval',
        seconds=15,
        id="save_state_job",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(_tz.utc)
    )

    # ลบ log เก่าเกิน 7 วัน — รันเที่ยงคืน BKK ทุกวัน
    scheduler.add_job(
        cleanup_logs_job,
        'cron',
        hour=0,
        minute=0,
        timezone='Asia/Bangkok',
        id="log_cleanup_job",
        max_instances=1,
        coalesce=True,
    )

    # สรุปผลประจำวัน — ส่ง Telegram ตามเวลา BKK ที่ตั้งไว้
    scheduler.add_job(
        daily_summary_job,
        'cron',
        hour=config.DAILY_SUMMARY_HOUR,
        minute=config.DAILY_SUMMARY_MINUTE,
        timezone='Asia/Bangkok',
        id="daily_summary_job",
        max_instances=1,
        coalesce=True,
    )

    # Watchdog / Health check — ทุก 1 นาที
    scheduler.add_job(
        run_watchdog,
        'interval',
        minutes=1,
        id="watchdog_job",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(_tz.utc)
    )

    # Heartbeat ถี่ — ทุก 15 วินาที (ให้ external supervisor detect loop hang ได้ไว)
    scheduler.add_job(
        write_heartbeat_job,
        'interval',
        seconds=15,
        id="heartbeat_job",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(_tz.utc)
    )

    async def post_init(application):
        # ลบ webhook ค้างก่อน start_polling ของ library เอง (bootstrap_retries=3
        # ของ run_polling ไม่พอถ้าเน็ต VPS สะดุดตอน startup — webhook เก่าจะค้าง
        # ฝั่ง Telegram แล้ว getUpdates ชนกันยาว (Conflict) จนกว่า process จะ
        # restart รอบหน้า ลอง retry หนักกว่านี้ตรงนี้กันไว้ก่อน)
        for _attempt in range(5):
            try:
                await application.bot.delete_webhook(drop_pending_updates=True)
                break
            except Exception as _e:
                log_error("DELETE_WEBHOOK_RETRY", f"attempt={_attempt+1}/5: {type(_e).__name__}: {_e}")
                await asyncio.sleep(2)

        wrap_bot(application)   # ← เพิ่มเวลานำหน้าทุก Telegram message
        application.bot_data["scheduler"] = scheduler
        application.bot_data["check_symbol_switch"] = check_symbol_switch

        # เริ่ม scheduler ก่อนงาน MT5 หนักๆ ด้านล่าง — heartbeat_job/jobs อื่นจะถูก
        # schedule ไว้ตั้งแต่ตอนนี้ ไม่ต้องรอ connect_mt5/restore/cleanup loop เสร็จก่อน
        # (run_scan/run_trail_sl/run_position_check เช็ค connect_mt5()/auto_active เองอยู่แล้ว
        # ถ้ายังต่อ MT5 ไม่ติดจะ no-op เฉยๆ ไม่ error)
        scheduler.start()
        config.write_heartbeat()

        import news_filter
        import asyncio
        asyncio.create_task(news_filter.fetch_news_loop(application))

        # แจ้ง MT5 connection status ตอน start
        from mt5_utils import connect_mt5
        now = now_bkk().strftime("%H:%M:%S")
        if connect_mt5():
            import config as _cfg
            config.write_heartbeat()
            restore_info = restore_runtime_state()
            config.write_heartbeat()
            await check_symbol_switch(startup=True)
            config.write_heartbeat()

            # ── auto_active reset เป็น False ทุกครั้งที่ restart (ค่า default ใน config.py)
            # เปิดอัตโนมัติให้กลับมาทำงานต่อ กันลืมเปิดมือหลัง restart/crash ───────────
            _auto_resumed = False
            if not _cfg.auto_active:
                _cfg.auto_active = True
                _auto_resumed = True
                log_event("AUTO_RESUME", "auto_active=False หลัง start → เปิดอัตโนมัติ")

            info = mt5.account_info()
            config.write_heartbeat()
            acc_txt = f"Account: {info.login} | Balance: {info.balance:.2f}" if info else ""
            mt5_to_bkk_hours = TZ_OFFSET - MT5_SERVER_TZ
            tz_txt = f"MT5 Server=UTC+{MT5_SERVER_TZ} | MT5->BKK=+{mt5_to_bkk_hours} | Display=BKK"
            log_msg = f"[{now}] MT5 connect ok | {acc_txt} | {tz_txt}"
            tg_msg  = (
                f"✅ *MT5 เชื่อมต่อสำเร็จ!*\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🤖 Bot เริ่มทำงาน\n"
                + (f"💰 Account: `{info.login}`\n📊 Balance: `{info.balance:.2f}`\n" if info else "")
                + f"📈 SYMBOL: `{_cfg.SYMBOL}`\n"
                + f"⏰ Scan ทุก 5 วินาที\n"
                + f"🕒 Time Mode: `MT5->BKK +{mt5_to_bkk_hours}`\n"
                + f"🕒 MT5 Server: `UTC+{MT5_SERVER_TZ}`\n"
                + f"🕒 Display: `BKK`\n"
                + f"📋 Strategy: {', '.join(STRATEGY_NAMES[k] for k,v in active_strategies.items() if v)}\n"
                + f"🕐 TF: {', '.join(tf for tf,on in TF_ACTIVE.items() if on) or 'ยังไม่ได้เลือก'}"
            )

            if _auto_resumed:
                tg_msg += f"\n⚡ Auto: `🟢ON` (เปิดอัตโนมัติหลัง restart)"

            if restore_info.get("restored"):
                restore_line = (
                    f"\n\n♻️ *Restore state สำเร็จ*"
                    f"\n🗂 Saved at: `{restore_info.get('saved_at','-')}`"
                    f"\n📦 pending map: `{restore_info.get('pending_order_tf', 0)}`"
                    f"\n📍 position tf: `{restore_info.get('position_tf', 0)}`"
                    f"\n📝 entry state: `{restore_info.get('entry_state', 0)}`"
                    f"\n📐 trail state: `{restore_info.get('trail_state', 0)}`"
                )
                tg_msg += restore_line
                print(f"[{now}] ♻️ restore_runtime_state ok: {restore_info}")
            else:
                print(f"[{now}] ℹ️ restore_runtime_state skipped: {restore_info.get('reason','unknown')}")

            # ── ลบ pending order M1 ที่เก่ากว่า 6 ชม. ──
            _deleted_tickets = []
            for sym_name in SYMBOL_CONFIG:
                config.write_heartbeat()
                old_orders = mt5.orders_get(symbol=sym_name)
                if not old_orders:
                    continue
                now_ts = _time.time()
                for o in old_orders:
                    if o.type not in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT,
                                      mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_SELL_STOP):
                        continue
                    comment = o.comment or ""
                    if not (comment.startswith("Bot_M1_") or comment == "Bot_M1"):
                        continue
                    age_hrs = (now_ts - o.time_setup) / 3600
                    if age_hrs < 6:
                        continue
                    r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                    if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                        _deleted_tickets.append(f"`{o.ticket}` ({age_hrs:.1f}h)")
                        print(f"[{now}] 🗑 Startup cleanup: ลบ M1 order #{o.ticket} (อายุ {age_hrs:.1f}h)")
            if _deleted_tickets:
                tickets_list = "\n".join(f"  • {t}" for t in _deleted_tickets)
                tg_msg += f"\n\n🗑 *ลบ pending M1 เก่า ({len(_deleted_tickets)} รายการ):*\n{tickets_list}"
        else:
            log_msg = f"❌ [{now}] MT5 เชื่อมต่อไม่ได้ — ตรวจสอบ MT5 และ credentials"
            tg_msg  = (
                f"❌ *MT5 เชื่อมต่อไม่ได้!*\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"กรุณาตรวจสอบ:\n"
                f"• เปิด MT5 ทิ้งไว้\n"
                f"• Login/Password ถูกต้อง\n"
                f"• Server: `{MT5_SERVER}`"
            )

        print(log_msg)
        try:
            await application.bot.send_message(
                chat_id=MY_USER_ID, text=tg_msg, parse_mode="Markdown"
            )
        except Exception as e:
            print(f"[{now}] ⚠️ ส่ง Telegram ไม่ได้: {e}")
            log_error("TG_SEND_ERROR", f"startup msg: {type(e).__name__}: {e}")

        active_tfs = [tf for tf, on in TF_ACTIVE.items() if on]
        save_runtime_state()
        print(f"[{now}] ✅ Auto Scan เริ่มทำงาน — สแกนทุก {SCAN_INTERVAL} นาที | TF: {active_tfs}")

    app.post_init = post_init
    # bootstrap_retries=3 กัน process ตายตอนสตาร์ท ถ้า delete_webhook timeout (เน็ต VPS สะดุด)
    # ค่า default=0 = ไม่ retry เลย -> TimedOut หลุดออกมาทำให้ทั้ง process exit เงียบ ๆ
    # allowed_updates=ALL_TYPES: บังคับขอรับทุก update type (รวม callback_query ของปุ่ม inline)
    #   override ค่า allowed_updates เก่าที่อาจค้างฝั่ง Telegram จาก webhook ของ instance เดิม
    #   drop_pending_updates=True: ล้าง update เก่าค้างคิว (รวม callback เก่า) ตอนเริ่ม
    app.run_polling(
        bootstrap_retries=3,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == '__main__':
    main()
