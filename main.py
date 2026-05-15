import MetaTrader5 as mt5
import asyncio
import time as _time
from datetime import datetime
from bot_log import log_event, log_error, setup_python_logging, cleanup_old_logs
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import *
from config import wrap_bot
from scanner import auto_scan
from trailing import (check_entry_candle_quality, check_engulf_trail_sl,
                      check_breakeven_tp, check_opposite_order_tp,
                      check_cancel_pending_orders, check_s1_zone_rules, check_s1_forward_confirm_rules, check_s6_trail,
                      check_limit_sweep)
from notifications import check_sl_tp_hits
from handlers.text_handler import start, handle_text
from handlers.callback_handler import handle_callback

_error_last_sent: dict = {}
_ERROR_COOLDOWN = 300  # วินาที — ไม่ส่ง error ซ้ำภายใน 5 นาที


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

    scheduler = AsyncIOScheduler()

    async def run_scan():
        try:
            await auto_scan(app)
        except Exception as e:
            await _tg_error(app, "run_scan", e)

    async def _close_btc_exposure_before_xau_switch():
        """ปิด position และลบ pending ของ BTCUSD ก่อนสลับกลับ XAUUSD"""
        btc_symbol = "BTCUSD.iux"
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
                log_event("ORDER_CANCELED", "BTC pending cleared before switching to XAUUSD.iux", symbol=btc_symbol, ticket=ticket)

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
                "magic": 234001,
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
                    "BTC position closed before switching to XAUUSD.iux",
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

    async def check_symbol_switch():
        """ตรวจตลาด XAUUSD — ถ้าปิดสลับไป BTCUSD ถ้าเปิดสลับกลับ"""
        import config
        from mt5_utils import connect_mt5
        if not connect_mt5():
            return
        try:
            xau_info = mt5.symbol_info("XAUUSD.iux")
            if xau_info is None:
                return
            xau_tick = mt5.symbol_info_tick("XAUUSD.iux")
            now_ts = int(datetime.now().timestamp())
            tick_ok = (
                xau_tick is not None
                and getattr(xau_tick, "time", 0) > 0
                and (now_ts - int(getattr(xau_tick, "time", 0))) <= 180
                and (float(getattr(xau_tick, "bid", 0.0)) > 0 or float(getattr(xau_tick, "ask", 0.0)) > 0)
            )
            xau_open = (xau_info.trade_mode != 0) and tick_ok
            print(
                f"[{now_bkk().strftime('%H:%M:%S')}] 🔎 symbol_check XAUUSD.iux "
                f"trade_mode={xau_info.trade_mode} "
                f"tick_time={getattr(xau_tick, 'time', 0)} "
                f"bid={getattr(xau_tick, 'bid', 0.0)} ask={getattr(xau_tick, 'ask', 0.0)} "
                f"tick_ok={tick_ok} => xau_open={xau_open}"
            )
        except Exception as e:
            print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ check_symbol_switch error: {e}")
            return
        if xau_open and config.SYMBOL != "XAUUSD.iux":
            if config.SYMBOL == "BTCUSD.iux":
                await _close_btc_exposure_before_xau_switch()
            set_runtime_symbol("XAUUSD.iux")
            save_runtime_state()
            await tg(app, f"🟡 *XAUUSD เปิดแล้ว* → สลับกลับ XAUUSD.iux")
            print(f"[{now_bkk().strftime('%H:%M:%S')}] 🔄 สลับกลับ XAUUSD.iux")
            if auto_active:
                await tg(app, "⚡ *สั่งสแกนทันทีหลังสลับ symbol* \n📈 SYMBOL: `XAUUSD.iux`")
                print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚡ trigger immediate scan after symbol switch -> XAUUSD.iux")
                await auto_scan(app)
        elif not xau_open and config.SYMBOL != "BTCUSD.iux":
            set_runtime_symbol("BTCUSD.iux")
            save_runtime_state()
            await tg(app, f"🔵 *XAUUSD ปิด* → สลับไป BTCUSD.iux")
            print(f"[{now_bkk().strftime('%H:%M:%S')}] 🔄 สลับไป BTCUSD.iux")
            if auto_active:
                await tg(app, "⚡ *สั่งสแกนทันทีหลังสลับ symbol* \n📈 SYMBOL: `BTCUSD.iux`")
                print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚡ trigger immediate scan after symbol switch -> BTCUSD.iux")
                await auto_scan(app)

    async def run_trail_sl():
        """Trail SL — รันได้เลย ไม่ต้องรอ"""
        if not auto_active:
            return
        from mt5_utils import connect_mt5
        if not connect_mt5():
            return
        try:
            await check_engulf_trail_sl(app)
            await check_s6_trail(app)
        except Exception as e:
            await _tg_error(app, "run_trail_sl", e)

    async def run_position_check():
        """Position management — รอ job ก่อนหน้าเสร็จก่อน (กัน race condition)"""
        if not auto_active:
            return
        from mt5_utils import connect_mt5
        if not connect_mt5():
            return
        try:
            await check_entry_candle_quality(app)
            await check_sl_tp_hits(app)
            await check_s1_zone_rules(app)
            await check_s1_forward_confirm_rules(app)
            await check_cancel_pending_orders(app)
            # await check_breakeven_tp(app)  # ปิดชั่วคราว
            await check_opposite_order_tp(app)
            await check_limit_sweep(app)
        except Exception as e:
            await _tg_error(app, "run_position_check", e)

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

    # Pattern scan ทุก 5 วินาที — guard ใน scanner กัน scan ซ้ำแท่งเดิม
    scheduler.add_job(
        run_scan,
        'interval',
        seconds=5,
        id="auto_scan_job",
        max_instances=3,
        misfire_grace_time=5,
        next_run_time=datetime.now(_tz2.utc)
    )

    # Trail SL ทุก 5 วินาที — รันได้เลย ไม่ต้องรอ
    from datetime import timezone as _tz
    scheduler.add_job(
        run_trail_sl,
        'interval',
        seconds=5,
        id="trail_sl_job",
        max_instances=3,
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

    async def post_init(application):
        wrap_bot(application)   # ← เพิ่มเวลานำหน้าทุก Telegram message
        application.bot_data["scheduler"] = scheduler
        application.bot_data["check_symbol_switch"] = check_symbol_switch

        # แจ้ง MT5 connection status ตอน start
        from mt5_utils import connect_mt5
        now = now_bkk().strftime("%H:%M:%S")
        if connect_mt5():
            await check_symbol_switch()
            restore_info = restore_runtime_state()
            info = mt5.account_info()
            acc_txt = f"Account: {info.login} | Balance: {info.balance:.2f}" if info else ""
            mt5_to_bkk_hours = TZ_OFFSET - MT5_SERVER_TZ
            tz_txt = f"MT5 Server=UTC+{MT5_SERVER_TZ} | MT5->BKK=+{mt5_to_bkk_hours} | Display=BKK"
            log_msg = f"[{now}] MT5 connect ok | {acc_txt} | {tz_txt}"
            tg_msg  = (
                f"✅ *MT5 เชื่อมต่อสำเร็จ!*\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🤖 Bot เริ่มทำงาน\n"
                + (f"💰 Account: `{info.login}`\n📊 Balance: `{info.balance:.2f}`\n" if info else "")
                + f"📈 SYMBOL: `{SYMBOL}`\n"
                + f"⏰ Scan ทุก 5 วินาที\n"
                + f"🕒 Time Mode: `MT5->BKK +{mt5_to_bkk_hours}`\n"
                + f"🕒 MT5 Server: `UTC+{MT5_SERVER_TZ}`\n"
                + f"🕒 Display: `BKK`\n"
                + f"📋 Strategy: {", ".join(STRATEGY_NAMES[k] for k,v in active_strategies.items() if v)}\n"
                + f"🕐 TF: {", ".join(tf for tf,on in TF_ACTIVE.items() if on) or 'ยังไม่ได้เลือก'}"
            )

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

        scheduler.start()

        print(log_msg)
        try:
            await application.bot.send_message(
                chat_id=MY_USER_ID, text=tg_msg, parse_mode="Markdown"
            )
        except Exception as e:
            print(f"[{now}] ⚠️ ส่ง Telegram ไม่ได้: {e}")

        active_tfs = [tf for tf, on in TF_ACTIVE.items() if on]
        save_runtime_state()
        print(f"[{now}] ✅ Auto Scan เริ่มทำงาน — สแกนทุก {SCAN_INTERVAL} นาที | TF: {active_tfs}")

    app.post_init = post_init
    app.run_polling()


if __name__ == '__main__':
    main()
