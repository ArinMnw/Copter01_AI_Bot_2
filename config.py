import MetaTrader5 as mt5
import asyncio
import copy
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ── Timezone offset สำหรับ display (Bangkok UTC+7) ──────────
# ถ้าเครื่อง Windows ตั้ง timezone ผิด ให้ปรับ TZ_OFFSET
TZ_OFFSET = 7   # UTC+7 Bangkok
MT5_SERVER_TZ = 1  # MT5 server UTC offset (IUXMarkets = UTC+1) — ลบออกจาก bar time ก่อนแปลง

def now_bkk() -> datetime:
    """คืนเวลา Bangkok โดยยึด MT5 server time ก่อน แล้วค่อย fallback เป็น MT5->BKK"""
    try:
        symbols = []
        if globals().get("SYMBOL"):
            symbols.append(SYMBOL)
        for sym in SYMBOL_CONFIG.keys():
            if sym not in symbols:
                symbols.append(sym)

        best_ts = None
        for sym in symbols:
            try:
                tick = mt5.symbol_info_tick(sym)
            except Exception:
                tick = None
            ts = int(getattr(tick, "time", 0) or 0) if tick else 0
            if ts > 0 and (best_ts is None or ts > best_ts):
                best_ts = ts

        if best_ts is not None:
            dt = mt5_ts_to_bkk(best_ts)
            if dt is not None:
                return dt
    except Exception:
        pass
    return datetime.now(timezone.utc) + timedelta(hours=TZ_OFFSET - MT5_SERVER_TZ)


def mt5_ts_to_bkk(ts: int | float | None) -> datetime | None:
    """แปลง MT5 server timestamp เป็นเวลา Bangkok ตามส่วนต่าง server -> BKK"""
    try:
        if ts is None:
            return None
        return datetime.fromtimestamp(int(ts), tz=timezone.utc) + timedelta(hours=TZ_OFFSET - MT5_SERVER_TZ)
    except Exception:
        return None


def fmt_mt5_bkk_ts(ts: int | float | None, fmt: str = "%H:%M:%S %d/%m/%Y") -> str:
    """format MT5 server timestamp เป็นเวลา Bangkok"""
    dt = mt5_ts_to_bkk(ts)
    return dt.strftime(fmt) if dt is not None else "-"


def set_runtime_symbol(new_symbol: str):
    """อัปเดต SYMBOL runtime ให้ทุกโมดูลสำคัญใช้ค่าล่าสุดตรงกัน
    เมื่อ symbol เปลี่ยนจริง → ล้าง per-symbol cache (hhll/amp/scanner) เพื่อกัน
    level/trend ของ symbol เก่าค้างปนเข้า scan ของ symbol ใหม่"""
    global SYMBOL
    changed = (SYMBOL != new_symbol)
    SYMBOL = new_symbol

    module_names = [
        "config",
        "scanner",
        "strategy8",
        "trailing",
        "mt5_utils",
        "notifications",
        "handlers.keyboard",
        "handlers.text_handler",
        "handlers.callback_handler",
        "handlers.btn_price",
        "handlers.btn_balance",
        "handlers.btn_buy",
        "handlers.btn_sell",
        "handlers.btn_order",
        "handlers.btn_pending",
        "handlers.btn_cancel_pending",
        "handlers.btn_auto",
    ]
    for name in module_names:
        mod = sys.modules.get(name)
        if mod is not None:
            setattr(mod, "SYMBOL", new_symbol)

    # ── ล้าง per-symbol cache เมื่อ symbol เปลี่ยนจริง (กัน stale data ปนข้าม symbol) ──
    # ใช้ sys.modules.get เพื่อเลี่ยง circular import (config เป็น base module)
    if changed:
        for mod_name, fn_name in (("hhll_swing", "clear_cache"),
                                  ("amp_trend",  "clear_cache"),
                                  ("scanner",    "clear_symbol_caches")):
            try:
                _m = sys.modules.get(mod_name)
                if _m is not None and hasattr(_m, fn_name):
                    getattr(_m, fn_name)()
            except Exception:
                pass

# ============================================================
#  SETTINGS
# ============================================================
TELEGRAM_TOKEN = "8731980788:AAHJ1_L3F44ZZbxR3yrPQhtZQzxgQE0d5s0"
MY_USER_ID     = 8666020453
SYMBOL         = "XAUUSD.iux"   # เปลี่ยน runtime โดย check_symbol_switch()
symbol_switch_in_progress = False  # True ระหว่าง check_symbol_switch กำลังสลับ symbol (กัน order race)

# ── config ต่อ symbol ─────────────────────────────────────────
SYMBOL_CONFIG = {
    "XAUUSD.iux": {"sl_buffer": 2.0,  "volume": 0.01},
    "BTCUSD.iux": {"sl_buffer": 50.0, "volume": 0.01},
}
MT5_LOGIN      = 2101114448
MT5_PASSWORD   = "cop04TERZ_18"
MT5_SERVER     = "IUXMarkets-Demo"

AUTO_VOLUME    = 0.01   # lot size สำหรับ auto trade (ฐานของ XAUUSD)


def points_scale() -> float:
    """
    Multiplier สำหรับ point/lot ตาม SYMBOL ปัจจุบัน
    XAUUSD = 1.0 (default), BTCUSD = 4.0
    ใช้ background ทุกที่ที่คำนวณ point → price (ไม่กระทบค่าใน Telegram UI)
    """
    if SYMBOL == "BTCUSD.iux":
        return 4.0
    return 1.0


def get_volume():
    """ดึง lot size ปัจจุบันของ auto trade — BTCUSD = AUTO_VOLUME × 4"""
    return round(AUTO_VOLUME * points_scale(), 2)
LOT_OPTIONS    = [0.01, 0.02, 0.03, 0.05, 0.10, 0.20]  # ตัวเลือก lot size
MAX_ORDERS     = 9999
SCAN_INTERVAL  = 1
TIMEFRAME      = mt5.TIMEFRAME_H1
TP_MULTIPLIER  = 1.0  # fallback RR 1:1
SWING_LOOKBACK = 20  # default
SWING_SUMMARY_MODE = "pivot"  # pair | pivot (used by scanner summary / trend export)
SWING_PIVOT_LEFT = 15
SWING_PIVOT_RIGHT = 10
TG_QUEUE_DEBUG = False
SLTP_AUDIT_DEBUG = False
TRADE_DEBUG = False

# จำนวนแท่งที่ดึงต่อ TF เพื่อให้ครอบคลุม ~20 ชั่วโมง
# TF เล็กต้องดึงเยอะกว่าเพื่อให้เห็น Swing ที่มีความหมาย
TF_LOOKBACK = {
    "M1":  300,   # 300 นาที = 5 ชั่วโมง
    "M5":  120,   # 120 x 5m = 10 ชั่วโมง
    "M15": 110,   # 110 x 15m = ~27 ชั่วโมง
    "M30": 110,   # 110 x 30m = ~2 วัน
    "H1":  110,   # 110 x 1h  = ~4 วัน
    "H4":  110,   # 110 x 4h  = ~18 วัน
    "H12": 110,   # 110 x 12h = ~55 วัน
    "D1":  110,   # 110 วัน
}
# ── Trail SL Group — TF ที่ใช้ตรวจ Engulf ตาม order TF ──────
# [0] = TF ของ order เอง (รอบสุดท้าย)
# [1:] = TF เล็กกว่าใน group (รอบแรก)
TRAIL_GROUPS = {
    "D1":  ["D1",  "H12", "H4"],
    "H12": ["H12", "H4",  "H1"],
    "H4":  ["H4",  "H1",  "M30"],
    "H1":  ["H1",  "M30", "M15"],
    "M30": ["M30", "M15", "M5"],
    "M15": ["M15", "M5",  "M1"],
    "M5":  ["M5",  "M1"],
    "M1":  ["M1"],
}

ZONE_BUFFER    = 0.5

# ── SL with ATR ─────────────────────────────────────────────────────────────
# ถ้าเปิด: SL_BUFFER() จะใช้ ATR × SL_ATR_MULT แทน fixed buffer
# (ใช้กับท่าที่เรียก SL_BUFFER: S1, S2, S3, S4, S9)
SL_ATR_ENABLED = True   # เปิด/ปิด feature
SL_ATR_MULT    = 2      # ตัวคูณ: 1=×1, 2=×2, ..., 5=×5  (default ×2)

# ── Pending-order limit guard ────────────────────────────────────────────────
# Broker จำกัดจำนวน pending orders (limit_orders) — ถ้าเต็มแล้ว bot ยังยิงซ้ำ
# จะโดน retcode 10033 "Orders limit reached" รัวๆ ทุก scan cycle → log บวม
# (เคสจริง 2026-05-31: BTC pending เต็ม → ORDER_FAILED 46,339 ครั้ง/วัน)
# Guard: pre-check orders_total ก่อนยิง — ถ้าใกล้เต็ม → skip เงียบ (ไม่ยิง broker
# + caller เข้า branch skipped ที่ dedup แล้ว) และเมื่อโดน 10033 → cooldown สั้นๆ
PENDING_LIMIT_GUARD_ENABLED = True   # เปิด/ปิด guard
PENDING_LIMIT_BUFFER        = 2      # เว้นช่อง pending ว่างกี่ตัวก่อนถึง broker cap
ORDERS_LIMIT_COOLDOWN_SEC   = 60     # หลังโดน 10033 → งดยิง order ใหม่กี่วินาที

def SL_BUFFER(atr=None):
    """ดึง SL buffer ตาม SYMBOL ปัจจุบัน
    - ถ้า SL_ATR_ENABLED=True และส่ง atr มา → คืน atr × SL_ATR_MULT
    - ไม่อย่างนั้น → คืน fixed buffer ตาม symbol
    """
    if SL_ATR_ENABLED and atr is not None:
        return float(atr) * float(SL_ATR_MULT)
    return SYMBOL_CONFIG.get(SYMBOL, SYMBOL_CONFIG["XAUUSD.iux"])["sl_buffer"]

# ── ท่าที่ 1: Zone filter mode ───────────────────────────────
# "zone"   = ต้องอยู่ใกล้ Swing Low/High (เดิม)
# "normal" = ไม่สนใจ zone (เข้าได้ทุก pattern ที่ผ่านเงื่อนไข)
S1_ZONE_MODE = "zone"

# ============================================================
#  กฎ Pattern ทั้งหมด:
#
#  ━━━ BUY ━━━
#  Pattern A (กลืนกิน เขียว 2 แท่ง):
#    [3]แดง [2]แดง [1]เขียวกลืน+คลุมไส้ [0]เขียวยืนยัน
#    Entry = 50% Body แท่ง[1] | SL = Low[1] - 200
#
#  Pattern B (ตำหนิ เขียว 2 แท่ง):
#    [3]แดง [2]เขียวตำหนิ(กลืนไม่คลุมไส้) [1]เขียวคลุมไส้[2] [0]เขียวยืนยัน
#    Entry = 50% Body แท่ง[2] | SL = Low[2] - 200
#
#  ━━━ SELL ━━━
#  Pattern A (กลืนกิน แดง 2 แท่ง):
#    [3]เขียว [2]เขียว [1]แดงกลืน+คลุมไส้ [0]แดงยืนยัน
#    Entry = 50% Body แท่ง[1] | SL = High[1] + 200
#
#  Pattern B (ตำหนิ แดง 2 แท่ง):
#    [3]เขียว [2]แดงตำหนิ(กลืนไม่คลุมไส้) [1]แดงคลุมไส้[2] [0]แดงยืนยัน
#    Entry = 50% Body แท่ง[2] | SL = High[2] + 200
#
#  ทุก Pattern ต้องเกิดที่ High/Low Zone
# ============================================================

auto_active = True
last_traded_candle = 0  # เก็บ timestamp แท่งที่เพิ่งเทรดไป (ป้องกันเปิดซ้ำในแท่งเดิม)

# Strategy ที่เปิดใช้งาน (True=เปิด, False=ปิด)
async def tg(app, text: str, parse_mode: str = "Markdown"):
    """ส่ง Telegram — เวลาถูกเพิ่มโดย _TgWrapper อัตโนมัติ"""
    try:
        await app.bot.send_message(chat_id=MY_USER_ID, text=text, parse_mode=parse_mode)
    except Exception as e:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ Telegram error: {e}")


class _TgWrapper:
    """Wrap app.bot.send_message ให้ส่งผ่าน queue/retry โดยไม่บล็อก logic หลัก"""
    _MIN_INTERVAL = 0.7   # วินาที — เร็วขึ้น แต่ยังเผื่อ flood control ไว้

    def __init__(self, bot):
        self._bot = bot
        self._send = bot.send_message
        self._last_send    = 0.0   # monotonic time ของข้อความล่าสุดที่ส่งสำเร็จ
        self._retry_until  = 0.0   # monotonic time ที่ flood control หมด

        self._queue = asyncio.PriorityQueue()
        self._counter = 0
        self._worker_task = None

    def _priority_for_text(self, text: str) -> int:
        text = text or ""
        high_markers = [
            "Limit Fill", "Entry จบ", "waiting_bad", "ปิด", "FAIL", "error",
            "SL Hit", "TP Hit", "retry ปิด", "S6i", "Trail SL"
        ]
        return 0 if any(m in text for m in high_markers) else 1

    def _preview(self, text: str, limit: int = 60) -> str:
        text = (text or "").replace("\n", " ")
        return text[:limit] + ("..." if len(text) > limit else "")

    async def _worker(self):
        import time
        from telegram.error import RetryAfter, TelegramError

        while True:
            priority, seq, payload = await self._queue.get()
            chat_id = payload["chat_id"]
            text = payload["text"]
            parse_mode = payload["parse_mode"]
            kwargs = payload["kwargs"]

            try:
                now = time.monotonic()
                if now < self._retry_until:
                    wait = self._retry_until - now
                    if TG_QUEUE_DEBUG:
                        print(f"[{now_bkk().strftime('%H:%M:%S')}] TG_QUEUE wait retry {wait:.1f}s qsize={self._queue.qsize()}")
                    await asyncio.sleep(wait)

                elapsed = time.monotonic() - self._last_send
                if elapsed < self._MIN_INTERVAL:
                    await asyncio.sleep(self._MIN_INTERVAL - elapsed)

                ts = now_bkk().strftime("%H:%M:%S")
                final_text = text
                # ── proactive: ตัดข้อความที่ยาวเกิน Telegram limit (4096) ก่อนส่ง ──
                # กัน TelegramError "Text is too long" / "Message is too long" ที่ทำให้ message ถูก drop
                if final_text and len(final_text) > 4096:
                    _cut = final_text.rfind('\n', 0, 4050)
                    if _cut < 2000:
                        _cut = 4050
                    final_text = final_text[:_cut] + "\n…_(ตัดข้อความยาว)_"
                if TG_QUEUE_DEBUG:
                    print(f"[{ts}] TG_QUEUE send p={priority} seq={seq} qsize={self._queue.qsize()} text={self._preview(text)}")
                await self._send(chat_id=chat_id, text=final_text, parse_mode=parse_mode, **kwargs)
                self._last_send = time.monotonic()
                if TG_QUEUE_DEBUG:
                    print(f"[{now_bkk().strftime('%H:%M:%S')}] TG_QUEUE sent p={priority} seq={seq}")
                # log ทุก message ที่ส่ง Telegram สำเร็จ (ยกเว้น Scan Summary ที่ยาวเกิน)
                if "Scan Summary" not in (text or ""):
                    try:
                        from bot_log import log_event as _le
                        _preview = (text or "").replace("\n", " | ")[:300]
                        _le("TG_SENT", _preview)
                    except Exception:
                        pass
            except RetryAfter as e:
                self._retry_until = time.monotonic() + e.retry_after
                print(f"[{now_bkk().strftime('%H:%M:%S')}] TG_QUEUE retry p={priority} seq={seq} after={e.retry_after}s text={self._preview(text)}")
                await self._queue.put((priority, seq, payload))
            except TelegramError as e:
                err_str = str(e)
                _retried = False
                _retry_err = None   # เก็บ error จาก retry path (ถ้า retry ก็ยัง fail)

                def _log_sent_retry(retry_text):
                    """log TG_SENT สำหรับ retry path ด้วย (เดิมไม่ log → ไม่รู้ว่าส่งสำเร็จ)"""
                    if "Scan Summary" not in (text or ""):
                        try:
                            from bot_log import log_event as _le
                            _le("TG_SENT", "[retry-plain] " + (retry_text or "").replace("\n", " | ")[:280])
                        except Exception:
                            pass

                # ── auto-fix: ข้อความยาวเกิน → truncate + retry ──
                if "too long" in err_str.lower():
                    try:
                        _cut = final_text.rfind('\n', 0, 4050)
                        if _cut < 2000:
                            _cut = 4050
                        _short = final_text[:_cut] + "\n…_(ข้อความถูกตัด)_"
                        try:
                            await self._send(chat_id=chat_id, text=_short, parse_mode=parse_mode, **kwargs)
                        except Exception:
                            await self._send(chat_id=chat_id, text=_short, parse_mode=None, **kwargs)
                        _retried = True
                        _log_sent_retry(_short)
                    except Exception as _re:
                        _retry_err = _re

                # ── auto-fix: Markdown parse error → retry ไม่มี formatting ──
                elif "parse entities" in err_str.lower() or "can't find end" in err_str.lower():
                    try:
                        await self._send(chat_id=chat_id, text=final_text, parse_mode=None, **kwargs)
                        _retried = True
                        _log_sent_retry(final_text)
                    except Exception as _re:
                        _retry_err = _re

                # ── auto-fix: Timed out → wait 3s + retry (Markdown → plain) ──
                elif "timed out" in err_str.lower():
                    try:
                        await asyncio.sleep(3)
                        try:
                            await self._send(chat_id=chat_id, text=final_text, parse_mode=parse_mode, **kwargs)
                        except Exception:
                            await self._send(chat_id=chat_id, text=final_text, parse_mode=None, **kwargs)
                        _retried = True
                        _log_sent_retry(final_text)
                    except Exception as _re:
                        _retry_err = _re

                if not _retried:
                    # ── retry ล้มเหลว → log TG_DROP พร้อม original error + retry error ──
                    _drop_detail = str(e)
                    if _retry_err:
                        _drop_detail += f" | retry_err={_retry_err}"
                    print(f"[{now_bkk().strftime('%H:%M:%S')}] TG_QUEUE drop p={priority} seq={seq} error={_drop_detail} text={self._preview(text)}")
                    try:
                        from bot_log import log_event as _le, log_error as _lerr
                        _msg = f"TelegramError: {_drop_detail} | text={self._preview(text, 120)}"
                        _le("TG_DROP", _msg)
                        _lerr("TG_DROP", _msg)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[{now_bkk().strftime('%H:%M:%S')}] TG_QUEUE unexpected p={priority} seq={seq} error={e} text={self._preview(text)}")
                try:
                    from bot_log import log_event as _le, log_error as _lerr
                    _msg = f"UnexpectedError: {e} | text={self._preview(text, 120)}"
                    _le("TG_DROP", _msg)
                    _lerr("TG_DROP", _msg)
                except Exception:
                    pass
            finally:
                self._queue.task_done()

    async def send_message(self, chat_id, text, parse_mode=None, **kwargs):
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())

        priority = self._priority_for_text(text)
        if text and "Scan Summary" in text:
            priority = 0
        elif text and any(marker in text for marker in [
            "ยกเลิก BUY LIMIT", "ยกเลิก SELL LIMIT", "ตั้ง BUY LIMIT", "ตั้ง SELL LIMIT",
            "เปิด BUY Market", "เปิด SELL Market", "ORDER_FAILED", "Ticket:`"
        ]):
            priority = 1
        self._counter += 1
        seq = self._counter
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "kwargs": kwargs,
        }
        await self._queue.put((priority, seq, payload))
        if TG_QUEUE_DEBUG:
            print(f"[{now_bkk().strftime('%H:%M:%S')}] TG_QUEUE queued p={priority} seq={seq} qsize={self._queue.qsize()} text={self._preview(text)}")
        return True

    def __getattr__(self, name):
        return getattr(self._bot, name)


def wrap_bot(app):
    """เรียกครั้งเดียวตอน post_init เพื่อ wrap bot.send_message"""
    app.bot = _TgWrapper(app.bot)


active_strategies = {
    1: True,   # ท่าที่ 1: กลืนกิน/ตำหนิ/ย้อนโครงสร้าง
    2: True,   # ท่าที่ 2: FVG (Parallel mode)
    3: True,   # ท่าที่ 3: DM SP
    4: True,   # ท่าที่ 4: นัยยะสำคัญ FVG
    5: False,  # ท่าที่ 5: Scalping
    6: True,   # ท่าที่ 6: 2 High 2 Low (ต่อเนื่องท่า 2/3)
    7: True,   # ท่าที่ 6i: 2 High 2 Low อิสระ (scan swing + ตั้ง order)
    8: False,  # ท่าที่ 8: กินไส้ Swing (limit ที่ swing high/low)
    9: False,  # ท่าที่ 9: RSI Divergence
    10: True,  # ท่าที่ 10: CRT TBS (Candle Range Theory + Three Bar Sweep)
    11: True,  # ท่าที่ 11: Fibo S1 (Fibonacci expansion จาก S1 pattern)
    12: False, # ท่าที่ 12: Range Trading (M5 only, standalone)
    13: False, # Strategy 13: EzAlgo V5 Supertrend
    14: True,  # ท่าที่ 14: Sweep RSI
    15: False, # ท่าที่ 15: Volume Profile POC + Absorption (Win Rate 85-90%)
}

STRATEGY_NAMES = {
    1: "ท่าที่ 1: กลืนกิน/ตำหนิ",
    2: "ท่าที่ 2: FVG",
    3: "ท่าที่ 3: DM SP",
    4: "ท่าที่ 4: นัยยะสำคัญ FVG",
    5: "ท่าที่ 5: Scalping",
    6: "ท่าที่ 6: 2H2L",
    7: "ท่าที่ 6i: 2H2L อิสระ",
    8: "ท่าที่ 8: กินไส้ Swing",
    9: "ท่าที่ 9: RSI Divergence",
    10: "ท่าที่ 10: CRT TBS",
    11: "ท่าที่ 11: Fibo S1",
    12: "ท่าที่ 12: Range Trading",
    13: "Strategy 13: EzAlgo V5",
    14: "ท่าที่ 14: Sweep RSI",
    15: "ท่าที่ 15: VP POC",
}

# ── Strategy 9: RSI Divergence ──────────────────────────────
# default ตาม indicator ในรูป: RSI 14 / close / pivot 5-5 / range 5-60
RSI9_PERIOD = 14
RSI9_APPLIED_PRICE = "close"
RSI9_PIVOT_LOOKBACK_RIGHT = 5
RSI9_PIVOT_LOOKBACK_LEFT = 5
RSI9_LOOKBACK_RANGE_MAX = 60
RSI9_LOOKBACK_RANGE_MIN = 5
RSI9_PLOT_BULLISH = True
RSI9_PLOT_HIDDEN_BULLISH = False
RSI9_PLOT_BEARISH = True
RSI9_PLOT_HIDDEN_BEARISH = False

# ── Strategy 12: Range Trading (M5 only, standalone) ─────────
S12_LOT_SIZE          = 0.01  # lot size ต่อ order
S12_ORDER_COUNT       = 3     # จำนวน order สูงสุดต่อ zone
S12_SL_POINTS         = 200   # ระยะ SL จาก entry (points)
S12_ZONE_POINTS       = 50    # ระยะ trigger จาก swing H/L เข้า zone
S12_LOOKBACK          = 100   # bars M5 ย้อนหลังสำหรับ swing detection (เพิ่มจาก 50 → ยึด swing กว้างขึ้น)
S12_COOLDOWN_SECONDS  = 1800  # cooldown หลัง SL hit (วินาที) — 1800 = 30 นาที
S12_MOMENTUM_BARS     = 3     # ถ้า M5 ล่าสุด N แท่งทิศเดียวกันทั้งหมด ไม่เปิด order ทวนทิศ

# Strategy 13: EzAlgo V5 (Supertrend crossover)
S13_SENSITIVITY       = 2.0
S13_SUPERTREND_ATR    = 11
S13_STOP_ATR_LEN      = 14
S13_STOP_ATR_MULT     = 4.0
S13_TP1_RR            = 0.7
S13_TP2_RR            = 1.2
S13_TP3_RR            = 1.5

# ── Strategy 14: Sweep RSI ────────────────────────────────────
# BUY  : จุดกลับตัวฝั่ง SELL (red engulf/rejection) → LL zone
#         → red reject (sweep LL + close red)
#         → RSI[reject] > RSI[LL] + RSI[reject] < 50
#         → Entry MARKET | TP = nearest HH/LH | SL = reject.L - SL_BUFFER
# SELL : mirror (green engulf/rejection → HH → green reject)
#
# SL ใช้ฟังก์ชัน SL_BUFFER(atr) เหมือนท่าอื่น
# (ถ้า SL_ATR_ENABLED=True จะใช้ ATR × SL_ATR_MULT อัตโนมัติ)
S14_RSI_PERIOD        = 14     # RSI period
S14_RSI_APPLIED_PRICE = "close"
S14_REVERSAL_LOOKBACK = 50     # bars ย้อนหาจุดกลับตัว + LL/HH zone
# เปิด/ปิด sub-pattern (ใช้ร่วมกันทั้ง BUY และ SELL)
S14_ENGULF            = False  # Engulf pattern (close เกิน LL/HH)
S14_SWEEP             = True   # Sweep pattern  (ไส้เกิน LL/HH แต่ปิดกลับมา)
S14_FLIP_ENABLED      = True   # Flip: ปิดฝั่งตรงข้ามทันทีเมื่อ signal ใหม่มา (per-TF)
S14_RSI_MIN_DIFF      = 1.0   # RSI divergence ต้องห่างกัน > นี้ (BUY: cur-ref > 1, SELL: ref-cur > 1)
# LL/HH ref เพิ่มเติมจาก HHLL module
# False (default) = ใช้ min low ของ reversal bars เท่านั้น
# True            = ใช้ HHLL HL (BUY) / HH (SELL) เป็น ref เพิ่มด้วย
#                   BUY : ll_val = max(reversal_ll, hhll.hl.price)
#                   SELL: hh_val = min(reversal_hh, hhll.hh.price)
S14_LL_USE_HHLL       = False

# ── Strategy 15: Volume Profile POC + Absorption ──────────────────
# Win rate อ้างอิง: 85-90% (POC defense + absorption institutional pattern)
# BUY : absorption ที่ POC หรือ VAL → Entry LIMIT | bypass trend filter ไม่ได้
# SELL: absorption ที่ POC หรือ VAH → Entry LIMIT
S15_LOOKBACK            = 100   # bars ย้อนหลังสำหรับคำนวณ Volume Profile
S15_ZONE_ATR_MULT       = 0.5   # tolerance zone = ATR × นี้ (auto-scale XAU/BTC)
S15_VAL_VAH_PCT         = 0.70  # % ของ volume ใน Value Area (standard 70%)
S15_ABSORPTION_WICK_PCT = 0.30  # wick ขั้นต่ำ (% ของ range) สำหรับ Pattern A
S15_USE_VAL_VAH         = True  # เปิดใช้ VAL/VAH เพิ่มจาก POC
S15_MIN_RR              = 1.0   # R:R ขั้นต่ำ

# ── ท่าที่ 2 FVG Mode ────────────────────────────────────────
# FVG_NORMAL  = True  → ตั้ง order ทุก TF อิสระ (TF เดียวก็ order)
# FVG_PARALLEL = True → กรอง FVG ซ้ำจาก TF คู่ขนาน (ต้อง ≥2 TF ซ้อนทับ)
# เปิดทั้งคู่ได้: parallel จะรวม gap ถ้าเจอ ≥2 TF, ปกติจะ order TF เดี่ยวที่ parallel ไม่ได้จับ
FVG_NORMAL = True
FVG_PARALLEL = True
S2_NORMAL_CONFIRM_LOOKBACK_BARS = 8  # S2 แบบปกติ: ย้อนดู S1/S3 ฝั่งเดียวกันกี่แท่งก่อนยอมใช้ order
S3_CONFIRM_LOOKBACK_BARS = 8         # S3: ย้อนดู S1/S2/S3 ฝั่งเดียวกันกี่แท่งก่อนยอมใช้ order

# ── Trail SL > Engulf Mode ───────────────────────────────────
# "separate" = แยก phase (TF เล็กกว่า -> TF order -> จบ)
# "combined" = รวม phase ตาม group TF และเลื่อน SL ต่อเนื่องเมื่อเจอ engulf
TRAIL_SL_MODE = "engulf"
TRAIL_SL_ENGULF_MODE = "combined"

# check_entry_candle_quality:
# "close"   = แท่ง entry สวนทาง → ปิดทันที แล้วเลือกได้ว่าจะ reverse market / reverse limit
# "classic" = แบบเดิม (waiting_bad → ปรับ SL/TP → รอแท่งถัดไป)
ENTRY_CANDLE_MODE = "close_percentage"
ENTRY_CLOSE_REVERSE_MARKET = False
ENTRY_CLOSE_REVERSE_LIMIT = True

# False = ปรับเฉพาะ SL ไม่เปลี่ยน TP
# True  = ปรับทั้ง SL และ TP ตามกติกา entry / waiting_next / waiting_bad
ENTRY_CANDLE_UPDATE_TP = False

# check_opposite_order_tp:
# "tp_close"   = ตั้ง TP ฝั่งตรงข้าม + ปิดตัวเก่าเมื่อ limit fill
# "sl_protect"  = ไม่ตั้ง TP ไม่ปิด → ตั้ง SL = entry ± spread แทน
OPPOSITE_ORDER_MODE = "sl_protect"

# ── Limit Guard ──────────────────────────────────────────────
# ยกเลิก limit ที่ entry สูงกว่า/ต่ำกว่า position ที่เปิดอยู่
# เมื่อราคาห่างจาก entry ของ position มากกว่า N จุด
LIMIT_GUARD = True
LIMIT_GUARD_POINTS = 200  # จำนวนจุด (point) ที่ถือว่าห่างเกินไป
LIMIT_GUARD_TF_MODE = "separate"  # "separate" = เฉพาะ TF เดียวกัน | "combined" = ดูทุก TF
ENGULF_MIN_POINTS = 20  # จำนวนจุดขั้นต่ำที่ close ต้องทะลุ high/low เดิมเพื่อถือว่า "กลืนกิน"

# ลบ LIMIT เมื่อแท่งยืนยันทะลุ TP/SL ตาม TF ที่เลือก
LIMIT_BREAK_CANCEL = False
LIMIT_BREAK_CANCEL_TF = {
    "M1":  True,
    "M5":  True,
    "M15": True,
    "M30": True,
    "H1":  True,
    "H4":  True,
    "H12": True,
    "D1":  True,
}

# ── Limit Trend Recheck: เช็ค trend ก่อน fill เมื่อราคาใกล้ entry ──
# ถ้า trend เปลี่ยนสวนทาง order ภายในระยะ N จุด → ยกเลิก limit
LIMIT_TREND_RECHECK = True
LIMIT_TREND_RECHECK_ROUNDS = 2    # จำนวนรอบ: 1=เช็คหลัง fill, 2=+รอ H/L, 3=+รอ H/L อีกรอบ
TREND_FILTER_SCAN_BLOCK = False   # False = ไม่ block ตอน scan ให้ Limit Recheck จัดการแทน

# ── Premium/Discount Zone Recheck ──────────────────────────────────
# เช็ค limit order ว่าอยู่ใน zone ที่ถูกต้องไหม (ตาม HHLL swing H/L)
# BUY ต้องอยู่ใต้ EQ (Discount), SELL ต้องอยู่เหนือ EQ (Premium)
# ตรวจ 3 รอบ: (1) เมื่อเจอ order (2) H หรือ L ใหม่ (3) ทั้ง H และ L ใหม่
# ยกเลิก order ถ้า < 2/3 รอบผ่าน
PD_ZONE_CHECK_ENABLED = True

# ── Recheck Mode: แยก (separate) หรือ รวม (combined 2/3 voting) ──────────────
# False = แยก (default) — แต่ละ check ตัดสินอิสระ, fail ทันที cancel/close
# True  = รวม — ต้องเปิดครบ RSI + Trend + PD, ใช้ 2/3 voting ร่วมกัน
RECHECK_COMBINED_MODE = False

# ── Pending RSI Recheck: เช็ค RSI ตอน order fill ──
# BUY ต้อง RSI < BUY_MAX, SELL ต้อง RSI > SELL_MIN ของ TF ที่ order นั้นใช้
PENDING_RSI_RECHECK_ENABLED = False
PENDING_RSI_PERIOD = 14
PENDING_RSI_APPLIED_PRICE = "close"
PENDING_RSI_BUY_MAX = 50.0
PENDING_RSI_SELL_MIN = 50.0
# Mode: 1 = ค่า RSI ปัจจุบัน (เดิม), 2 = State machine crossover, 3 = ทั้งคู่
PENDING_RSI_RECHECK_MODE = 2
# Mode 2 levels
RSI_MODE2_OB  = 70.0   # Overbought — cross ลง → SELL_ONLY
RSI_MODE2_OS  = 30.0   # Oversold   — cross ขึ้น → BUY_ONLY
RSI_MODE2_MID = 50.0   # Midline    — cross ขึ้น/ลง เปลี่ยน state

# ── Near Approach Cancel: ยกเลิก limit เมื่อราคาเข้าใกล้แล้วกลับตัว ──
# SELL LIMIT: high เข้ามาใน N pt ของ entry แล้ว bar ถัดไปกลับออก → ยกเลิก
# BUY LIMIT:  low เข้ามาใน N pt ของ entry แล้ว bar ถัดไปกลับออก → ยกเลิก
NEAR_APPROACH_CANCEL_ENABLED = False
NEAR_APPROACH_CANCEL_POINTS = 200  # ระยะใกล้สุดที่ถือว่า "เข้าใกล้" (points)
NEAR_APPROACH_CANCEL_LOOKBACK = 3  # จำนวน bars ย้อนหลังที่ตรวจ approach

# แท่งถัดจาก detect bar ปิดสวนทาง body ≥ 35% → cancel order
# BUY LIMIT: แท่งแดง body ≥ 35% / SELL LIMIT: แท่งเขียว body ≥ 35%
CANCEL_NEXT_BAR_BODY_ENABLED = False

# ── SL Guard ─────────────────────────────────────────────────
# เมื่อใน TF นั้น BUY โดน SL ครบ N ครั้ง → ยกเลิก pending BUY ที่ใกล้ (<NEAR pts)
# + บล็อกการตั้ง BUY LIMIT ใหม่ จนกว่าจะเกิด Swing Low ใหม่ใน TF นั้น
# (SELL เหมือนกัน สลับทิศ)
SL_GUARD_ENABLED    = False  # แบบแยก Per-TF (เปิดได้ทีละ 1 mode)
SL_GUARD_COUNT      = 2    # จำนวน SL hits ที่ trigger guard
SL_GUARD_NEAR_POINTS = 200  # ระยะ (points) ที่ถือว่า "ใกล้" pending order

# ── SL Guard Loss ────────────────────────────────────────────
# นับ close ที่ขาดทุนเกิน threshold ว่าเป็น "SL hit" ด้วย (ไม่ว่าจะปิดด้วยเหตุใด)
# เช่น manual close / bot close ที่ profit < -5$ → นับ +1 เหมือน SL hit
SL_GUARD_LOSS_ENABLED   = False
SL_GUARD_LOSS_THRESHOLD = 5.0   # USD — ขาดทุนเกินนี้ถึงนับ
SL_GUARD_CLOSE_ON_ACTIVATE = True  # ปิด open position ฝั่งเดียวกัน/TF เดียวกันเมื่อ Guard activate

# ── SL Guard Combined TF ──────────────────────────────────────
# นับ SL รวมข้าม TF ใน group เดียวกัน
# เมื่อ count รวม ≥ threshold → ล็อกทุก TF ใน group
# แต่ละ TF unblock อิสระเมื่อเจอ swing low/high ของตัวเอง
SL_GUARD_COMBINED_ENABLED = False
SL_GUARD_COMBINED_COUNT   = 2       # จำนวน SL รวม (จากทุก TF ใน group) ที่ trigger
SL_GUARD_COMBINED_TFS: list = ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1"]

# ── SL Guard Group ────────────────────────────────────────────
# นับ SL ต่าม FVG Parallel Group structure (หลาย group อิสระ)
# เมื่อ count รวมใน group ≥ threshold → ล็อกทุก TF ใน group นั้น
# เมื่อ activate → ปิด position ทั้งหมดของ side นั้น (ไม่สน TF)
# แต่ละ TF unblock อิสระเมื่อเจอ swing low/high ของตัวเอง
SL_GUARD_GROUP_ENABLED = True   # default mode
SL_GUARD_GROUP_COUNT   = 2
SL_GUARD_GROUP_GROUPS: list = [
    ["H4",  "H12", "D1"],
    ["H1",  "H4",  "H12"],
    ["M30", "H1",  "H4"],
    ["M15", "M30", "H1"],
    ["M5",  "M15", "M30"],
    ["M1",  "M5",  "M15"],
    ["M1",  "M5"],
]

# ── Limit Sweep ──────────────────────────────────────────────
# เมื่อ position ถูก fill แล้วแท่งจบสวนทาง (BUY→แดง close<prevLow / SELL→เขียว close>prevHigh)
# → ปิด position + ยกเลิก limit ทั้งหมดใน TF นั้น เหลือเฉพาะตัวใกล้ LL/HH
# → ถ้าไม่มี limit ใกล้ LL/HH → ตั้ง S8 ที่ LL/HH
LIMIT_SWEEP = False

# ── Delay SL ────────────────────────────────────────────────
# "off"   = ตั้ง SL ทันทีตอนส่ง order (ยกเว้น S8 ที่รอ breakout เสมอ)
# "time"  = ส่ง order SL=0 แล้วตั้ง SL ใน 10% สุดท้ายของ TF (M1=6วิ, M5=30วิ, …)
# "price" = ส่ง order SL=0 แล้วตั้ง SL เมื่อ BUY: ask>entry+spread / SELL: bid<entry-spread
DELAY_SL_MODE = "off"

# ── Trail SL Immediate ───────────────────────────────────────
# True  = Trail SL ทำงานทันทีหลัง fill (ไม่รอ entry candle done)
# False = รอ entry candle quality = "done" ก่อน (default)
TRAIL_SL_IMMEDIATE = True

# ── เปิด/ปิดฟังก์ชันหลักแยกกัน (toggle จาก Telegram) ────────
# True  = เปิดใช้งาน (default)
# False = ปิดการทำงาน ฟังก์ชัน return early
TRAIL_SL_ENABLED = True
ENTRY_CANDLE_ENABLED = False
OPPOSITE_ORDER_ENABLED = True

# ── Trail SL Focus New Opposite ─────────────────────────────
# เมื่อ BUY position กำไร > threshold + spread → ไม่ trail BUY นั้น
# ให้ trail เฉพาะ SELL ฝั่งตรงข้าม (position หรือ pending limit) ที่พึ่งเปิดแทน
# ฝั่ง SELL ทำงานสลับกัน
TRAIL_SL_FOCUS_NEW_ENABLED = True
TRAIL_SL_FOCUS_NEW_POINTS = 100  # 100 | 200 | 300 | 500
TRAIL_SL_FOCUS_NEW_TF_MODE = "combined"  # "separate" = จับคู่ TF เดียวกัน | "combined" = ข้าม TF
TRAIL_SL_REVERSAL_OVERRIDE_ENABLED = True

# ── Entry Candle Focus New Opposite ─────────────────────────
# เงื่อนไขเดียวกับ Trail SL Focus New แต่ใช้กับ check_entry_candle_quality
# BUY position กำไร > threshold + spread + มี opposite SELL → ข้าม ECM ของ BUY นั้น
# SELL ทำงานสลับกัน
ENTRY_CANDLE_FOCUS_NEW_ENABLED = True
ENTRY_CANDLE_FOCUS_NEW_POINTS = 100  # 100 | 200 | 300 | 500
ENTRY_CANDLE_FOCUS_NEW_TF_MODE = "combined"  # "separate" | "combined"

# ── Trend Filter (Scan Trend) ───────────────────────────────
# กรอง signal ตาม trend ที่คำนวณจาก swing H/L
# per-TF  = checklist ของ TF ที่เปิด filter "ของใครของมัน"
#           (signal TF X ติ๊กไว้ → filter ด้วย trend ของ TF X เอง)
# higher  = เลือก 1 TF — ทุก signal filter ด้วย trend ของ TF นั้น
# เปิดทั้งคู่ได้ (signal ต้องผ่านทั้ง 2 ถ้ามีผล)
# กฎ (strong trend เท่านั้น — tentative/sideway ผ่านหมด):
#   BULL + ไม่ break down → BUY only
#   BULL + break down     → both
#   BEAR + ไม่ break up   → SELL only
#   BEAR + break up       → both
TREND_FILTER_PER_TF = {
    "M1":  True,
    "M5":  True,
    "M15": True,
    "M30": True,
    "H1":  True,
    "H4":  True,
    "H12": True,
    "D1":  True,
}
TREND_FILTER_HIGHER_TF_ENABLED = False
TREND_FILTER_HIGHER_TF = "H4"   # M15 | M30 | H1 | H4 | H12 | D1
TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED = True
TREND_FILTER_SIDEWAY_HHLL = True   # True = SIDEWAY+LH→block BUY / SIDEWAY+HL→block SELL

# Mode ตัดสิน signal:
#   "basic"    — ทิศ trend ล้วน ๆ (BULL→BUY only, BEAR→SELL only, SW→both) ทุก strength
#   "breakout" — เฉพาะ strong + มี exception ตอน breakout
#                BULL strong + ไม่ break_down → BUY only / + break_down → ผ่านทั้งคู่
#                BEAR strong + ไม่ break_up   → SELL only / + break_up   → ผ่านทั้งคู่
#                weak / sideway / unknown → ผ่านทั้งคู่
TREND_FILTER_MODE = "breakout"

# ── Strong-Trend Block สำหรับท่า bypass ───────────────────────
# ปกติ S9/S10/S11/S13/S14 ข้าม trend filter (เป็นท่า reversal/mean-reversion)
# แต่ข้อมูลจริง (XAU 26 พ.ค.+) พบว่า counter-trend ตอนเทรนด์ "strong"
# แพ้บ่อย (46% win, net -314) → ถ้าเปิด flag นี้จะบล็อก signal ที่สวน strong trend
# เฉพาะท่าใน STRONG_TREND_BLOCK_SIDS (default OFF — ไม่กระทบ behavior เดิม)
STRONG_TREND_BLOCK_ENABLED = False
STRONG_TREND_BLOCK_SIDS = [9, 10, 11, 13, 14, 15]

# ── Strategy 10: CRT TBS — runtime mode (constants ที่ helper ใช้ภายหลังอยู่ด้านล่าง) ──
# Bar mode: "2bar" (classic CRT — sweep+close ในแท่งเดียว) หรือ "3bar" (TBS — sweep+confirm แยก)
CRT_BAR_MODE = "2bar"
# Min sweep depth: sweep wick ต้องทะลุ parent อย่างน้อยกี่ % ของ parent range (กัน micro-sweep)
CRT_SWEEP_DEPTH_PCT = 0.10   # 10% of parent range
# Entry mode:
#   "htf" — เข้า market บน HTF ทันทีตอน detect (SL ใหญ่)
#   "mtf" (default) — HTF detect → arm → ลงไป LTF รอ color shift → entry (SL เล็ก, RR ดี)
CRT_ENTRY_MODE = "mtf"

# กลุ่ม TF คู่ขนาน — ถ้า gap ของ TF เล็กอยู่ใน gap ของ TF ใหญ่
# ให้ใช้ TF เล็กเป็นหลัก (entry แม่นกว่า) และยกเลิก TF อื่นในกลุ่ม
FVG_PARALLEL_GROUPS = [
    ["H4",  "H12", "D1"],
    ["H1",  "H4",  "H12"],
    ["M30", "H1",  "H4"],
    ["M15", "M30", "H1"],
    ["M5",  "M15", "M30"],
    ["M5",  "M15"],
    ["M1",  "M5"],
]

# ตัวเลือก Scan Interval (นาที)
INTERVAL_OPTIONS = [1, 5, 15, 30, 60, 240]

# ตัวเลือก Timeframe
TF_OPTIONS = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "H12": mt5.TIMEFRAME_H12,
    "D1":  mt5.TIMEFRAME_D1,
}
# Timeframe ที่เปิดใช้งาน (สแกนทุก TF ที่ True พร้อมกัน)
TF_ACTIVE = {
    "M1":  True,
    "M5":  True,
    "M15": True,
    "M30": True,
    "H1":  True,
    "H4":  True,
    "H12": True,
    "D1":  True,
}
TF_CURRENT = "H1"  # ใช้สำหรับเมนูตั้งค่า (backward compat)


# ── Global State ────────────────────────────────────────────────
TF_MINUTES = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 60, "H4": 240, "H12": 720, "D1": 1440,
}

# ANSI rainbow colors สำหรับแต่ละ TF (terminal log)
TF_COLOR = {
    "M1":  "[38;5;196m",  # แดงสด
    "M5":  "[38;5;208m",  # ส้ม
    "M15": "[38;5;226m",  # เหลืองสด
    "M30": "[38;5;46m",   # เขียวสด
    "H1":  "[38;5;51m",   # ฟ้าอ่อน
    "H4":  "[38;5;27m",   # น้ำเงิน
    "H12": "[38;5;129m",  # ม่วง
    "D1":  "[38;5;201m",  # ม่วงชมพู
}
RESET  = "\033[0m"
BOLD   = "\033[1m"
C_ENTRY = "\033[38;5;226m"   # เหลือง — Entry
C_SL    = "\033[38;5;196m"   # แดง    — SL
C_TP    = "\033[38;5;46m"    # เขียว  — TP

STATE_FILE = "bot_state.json"

# ── Triple Scale-Out (TSO) — Config ───────────────────────────
# เปิด/ปิด ผ่านปุ่ม Telegram (📈 Scale-Out 4X)
# เมื่อ ON:
#   - Pending/Limit order ใหม่ ใช้ volume × SCALE_OUT_MULTIPLIER (0.01 × 4 = 0.04) เสมอ
#   - effective steps เสมอ 4 ขั้น
#   - ทั่วไป:  [min(200pt,TP), min(300pt,TP), min(600pt,TP), TP]
#   - S10:    [min(200pt,TP), min(300pt,TP), TP/2, TP]
#   - S13:    สร้าง 4 orders แยก (ไม่ partial-close) — ไม่ลบตอน toggle OFF
#   - เมื่อราคาผ่าน entry ไปครบ step จะปิด lot ทีละ SCALE_OUT_TP_LOT
# เมื่อ OFF:
#   - Position ที่เปิดอยู่ (non-S13): ปิดทั้งหมด
#   - Pending ที่ยังไม่ fill (non-S13): ยกเลิก + สร้างใหม่ด้วย lot เดิม
SCALE_OUT_ENABLED       = True                    # default ON
SCALE_OUT_MULTIPLIER    = 4                       # ×4 lot เสมอ
SCALE_OUT_TP_POINTS     = [200, 300, 600]         # ทั่วไป: base steps (pt) ก่อน cap ด้วย TP
S10_SCALE_OUT_TP_POINTS = [200, 300]              # S10: base steps (pt) ก่อน TP/2 และ TP
SCALE_OUT_TP_LOT        = 0.04                    # lot per step


def scale_out_total_volume() -> float:
    """รวม lot ทั้งหมดของ TSO order = AUTO_VOLUME × points_scale × SCALE_OUT_MULTIPLIER"""
    return round(AUTO_VOLUME * points_scale() * SCALE_OUT_MULTIPLIER, 2)


def scale_out_per_tp_volume() -> float:
    """ขนาด lot ที่จะปิดต่อขั้น = SCALE_OUT_TP_LOT × points_scale"""
    return round(float(SCALE_OUT_TP_LOT) * points_scale(), 2)


def scale_out_tp_distances() -> list:
    """ระยะ TP แต่ละขั้น (หน่วยราคา) — auto scale BTC ×4 ผ่าน points_scale"""
    try:
        info = mt5.symbol_info(SYMBOL)
        point = float(getattr(info, "point", 0.01) or 0.01)
    except Exception:
        point = 0.01
    return [float(pts) * point * points_scale() for pts in SCALE_OUT_TP_POINTS]


def compute_tso_effective_steps(tp_orig_dist: float, sid="") -> list:
    """
    คำนวณ effective TP steps (หน่วยราคา) สำหรับ TSO — เสมอ 4 steps

    ทั่วไป (non-S10):  [min(200pt,TP), min(300pt,TP), min(600pt,TP), TP]
      TP 100pt → [100, 100, 100, 100]
      TP 500pt → [200, 300, 500, 500]
      TP 800pt → [200, 300, 600, 800]
      TP 1200pt → [200, 300, 600, 1200]

    S10:               [min(200pt,TP), min(300pt,TP), TP/2, TP]
      TP 100pt → [100, 100,  50, 100]
      TP 500pt → [200, 300, 250, 500]
      TP 800pt → [200, 300, 400, 800]
      TP 1200pt → [200, 300, 600, 1200]

    Return: list ของ 4 step distances (price units)
    """
    try:
        info = mt5.symbol_info(SYMBOL)
        point = float(getattr(info, "point", 0.01) or 0.01)
    except Exception:
        point = 0.01
    scale = points_scale()
    tp_orig_dist = float(tp_orig_dist or 0.0)
    if tp_orig_dist <= 0:
        return []

    p200 = 200.0 * point * scale
    p300 = 300.0 * point * scale
    p600 = 600.0 * point * scale

    if str(sid) == "10":
        s1 = min(p200, tp_orig_dist)
        s2 = min(p300, tp_orig_dist)
        s3 = tp_orig_dist / 2.0
        s4 = tp_orig_dist
    else:
        s1 = min(p200, tp_orig_dist)
        s2 = min(p300, tp_orig_dist)
        s3 = min(p600, tp_orig_dist)
        s4 = tp_orig_dist

    return [s1, s2, s3, s4]


_RUNTIME_DEFAULTS = {
    "AUTO_VOLUME": AUTO_VOLUME,
    "SCAN_INTERVAL": SCAN_INTERVAL,
    "TG_QUEUE_DEBUG": TG_QUEUE_DEBUG,
    "SLTP_AUDIT_DEBUG": SLTP_AUDIT_DEBUG,
    "TRADE_DEBUG": TRADE_DEBUG,
    "active_strategies": copy.deepcopy(active_strategies),
    "FVG_NORMAL": FVG_NORMAL,
    "FVG_PARALLEL": FVG_PARALLEL,
    "ENTRY_CANDLE_MODE": ENTRY_CANDLE_MODE,
    "ENTRY_CLOSE_REVERSE_MARKET": ENTRY_CLOSE_REVERSE_MARKET,
    "ENTRY_CLOSE_REVERSE_LIMIT": ENTRY_CLOSE_REVERSE_LIMIT,
    "ENTRY_CANDLE_UPDATE_TP": ENTRY_CANDLE_UPDATE_TP,
    "OPPOSITE_ORDER_MODE": OPPOSITE_ORDER_MODE,
    "LIMIT_GUARD": LIMIT_GUARD,
    "LIMIT_GUARD_POINTS": LIMIT_GUARD_POINTS,
    "LIMIT_GUARD_TF_MODE": LIMIT_GUARD_TF_MODE,
    "ENGULF_MIN_POINTS": ENGULF_MIN_POINTS,
    "LIMIT_BREAK_CANCEL": LIMIT_BREAK_CANCEL,
    "LIMIT_BREAK_CANCEL_TF": copy.deepcopy(LIMIT_BREAK_CANCEL_TF),
    "LIMIT_TREND_RECHECK": LIMIT_TREND_RECHECK,
    "LIMIT_TREND_RECHECK_ROUNDS": LIMIT_TREND_RECHECK_ROUNDS,
    "SL_ATR_ENABLED": SL_ATR_ENABLED,
    "SL_ATR_MULT": SL_ATR_MULT,
    "PENDING_RSI_RECHECK_ENABLED": PENDING_RSI_RECHECK_ENABLED,
    "PENDING_RSI_PERIOD": PENDING_RSI_PERIOD,
    "PENDING_RSI_APPLIED_PRICE": PENDING_RSI_APPLIED_PRICE,
    "PENDING_RSI_BUY_MAX": PENDING_RSI_BUY_MAX,
    "PENDING_RSI_SELL_MIN": PENDING_RSI_SELL_MIN,
    "LIMIT_SWEEP": LIMIT_SWEEP,
    "DELAY_SL_MODE": DELAY_SL_MODE,
    "TRAIL_SL_IMMEDIATE": TRAIL_SL_IMMEDIATE,
    "TRAIL_SL_ENABLED": TRAIL_SL_ENABLED,
    "ENTRY_CANDLE_ENABLED": ENTRY_CANDLE_ENABLED,
    "TRAIL_SL_REVERSAL_OVERRIDE_ENABLED": TRAIL_SL_REVERSAL_OVERRIDE_ENABLED,
    "OPPOSITE_ORDER_ENABLED": OPPOSITE_ORDER_ENABLED,
    "TRAIL_SL_FOCUS_NEW_ENABLED": TRAIL_SL_FOCUS_NEW_ENABLED,
    "TRAIL_SL_FOCUS_NEW_POINTS": TRAIL_SL_FOCUS_NEW_POINTS,
    "TRAIL_SL_FOCUS_NEW_TF_MODE": TRAIL_SL_FOCUS_NEW_TF_MODE,
    "ENTRY_CANDLE_FOCUS_NEW_ENABLED": ENTRY_CANDLE_FOCUS_NEW_ENABLED,
    "ENTRY_CANDLE_FOCUS_NEW_POINTS": ENTRY_CANDLE_FOCUS_NEW_POINTS,
    "ENTRY_CANDLE_FOCUS_NEW_TF_MODE": ENTRY_CANDLE_FOCUS_NEW_TF_MODE,
    "TREND_FILTER_PER_TF": copy.deepcopy(TREND_FILTER_PER_TF),
    "TREND_FILTER_HIGHER_TF_ENABLED": TREND_FILTER_HIGHER_TF_ENABLED,
    "TREND_FILTER_HIGHER_TF": TREND_FILTER_HIGHER_TF,
    "TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED": TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED,
    "TREND_FILTER_SIDEWAY_HHLL": TREND_FILTER_SIDEWAY_HHLL,
    "TREND_FILTER_MODE": TREND_FILTER_MODE,
    "CRT_BAR_MODE": CRT_BAR_MODE,
    "CRT_SWEEP_DEPTH_PCT": CRT_SWEEP_DEPTH_PCT,
    "CRT_ENTRY_MODE": CRT_ENTRY_MODE,
    "RSI9_PLOT_BULLISH": RSI9_PLOT_BULLISH,
    "RSI9_PLOT_HIDDEN_BULLISH": RSI9_PLOT_HIDDEN_BULLISH,
    "RSI9_PLOT_BEARISH": RSI9_PLOT_BEARISH,
    "RSI9_PLOT_HIDDEN_BEARISH": RSI9_PLOT_HIDDEN_BEARISH,
    "NEAR_APPROACH_CANCEL_ENABLED": NEAR_APPROACH_CANCEL_ENABLED,
    "NEAR_APPROACH_CANCEL_POINTS": NEAR_APPROACH_CANCEL_POINTS,
    "NEAR_APPROACH_CANCEL_LOOKBACK": NEAR_APPROACH_CANCEL_LOOKBACK,
    "TF_ACTIVE": copy.deepcopy(TF_ACTIVE),
    "TF_CURRENT": TF_CURRENT,
    "SWING_SUMMARY_MODE": SWING_SUMMARY_MODE,
    "SWING_PIVOT_LEFT": SWING_PIVOT_LEFT,
    "SWING_PIVOT_RIGHT": SWING_PIVOT_RIGHT,
    "SCALE_OUT_ENABLED": SCALE_OUT_ENABLED,
    # S14 sub-pattern toggles (runtime-resettable)
    "S14_ENGULF":        S14_ENGULF,
    "S14_SWEEP":         S14_SWEEP,
    "S14_LL_USE_HHLL":   S14_LL_USE_HHLL,
    "S14_FLIP_ENABLED":  S14_FLIP_ENABLED,
    # S15 config (runtime-resettable)
    "S15_USE_VAL_VAH":   S15_USE_VAL_VAH,
    "S15_LOOKBACK":      S15_LOOKBACK,
    "S15_MIN_RR":        S15_MIN_RR,
}

fvg_pending       = {}   # {key: {tf, signal, entry, sl, tp, gap_top, gap_bot, candle_key}}
pb_pending        = {}   # {key: {tf, signal, entry, sl, tp, candle_key}} Pattern B วิธี 2
s3_maru_pending   = {}   # {key: {tf, direction, entry, sl, tp, candle_time}} ท่า3 Marubozu รอยืนยัน
last_traded_per_tf = {}  # {tf_name: candle_timestamp} กัน order ซ้ำ
last_traded_sid_tf = {}  # {tf_name: {sid: candle_timestamp}} กัน order แท่งติดกันแยก sid
tracked_positions  = {}  # {ticket: {symbol, type, price_open, sl, tp}} ตรวจ SL/TP hit
# ── Triple Scale-Out (TSO) — state ────────────────────────────
# {ticket: {direction, entry, original_volume, per_tp_volume,
#           tp_distances (list of price units), step (0..3), is_pending}}
scale_out_state    = {}  # ทยอยปิด 3 ขั้น (เฉพาะ pending/limit ที่เปิดตอน TSO=ON)


def _int_key_dict(d):
    out = {}
    for k, v in (d or {}).items():
        try:
            out[int(k)] = v
        except (TypeError, ValueError):
            continue
    return out


def _sync_runtime_exports():
    sync_modules = [
        "main",
        "scanner",
        "pending",
        "trailing",
        "notifications",
        "handlers.keyboard",
        "handlers.callback_handler",
        "handlers.text_handler",
        "handlers.btn_price",
        "handlers.btn_balance",
        "handlers.btn_buy",
        "handlers.btn_sell",
        "handlers.btn_order",
    ]
    for module_name in sync_modules:
        module = sys.modules.get(module_name)
        if not module:
            continue
        for key in _RUNTIME_DEFAULTS:
            if hasattr(module, key):
                setattr(module, key, globals()[key])


def reset_runtime_config_to_defaults(save_state: bool = True):
    """รีเซทค่า config runtime กลับไปตามค่าเริ่มต้นในไฟล์ config.py"""
    for key, default in _RUNTIME_DEFAULTS.items():
        current = globals().get(key)
        if isinstance(default, dict) and isinstance(current, dict):
            current.clear()
            current.update(copy.deepcopy(default))
        elif isinstance(default, list) and isinstance(current, list):
            current[:] = copy.deepcopy(default)
        else:
            globals()[key] = copy.deepcopy(default)

    _sync_runtime_exports()
    if save_state:
        save_runtime_state()


def engulf_min_price() -> float:
    """แปลงจำนวน point ของ engulf ขั้นต่ำเป็นหน่วยราคา (BTC = 4× ของ XAU)"""
    try:
        info = mt5.symbol_info(SYMBOL)
        point = float(getattr(info, "point", 0.01) or 0.01)
    except Exception:
        point = 0.01
    return float(ENGULF_MIN_POINTS) * point * points_scale()


# ── Strategy 10: CRT TBS — point constants (CRT_BAR_MODE/PCT อยู่ด้านบน) ──
# Parent range ที่เล็กกว่านี้จะข้าม (กัน setup จิ๋วใน sideway แคบ)
CRT_MIN_RANGE_POINTS = 200   # 200 point = ~$2.00 บน XAU
# SL บัฟเฟอร์ จาก wick ของ sweep candle
CRT_SL_BUFFER_POINTS = 50    # 50 point = ~$0.50 บน XAU


def crt_min_range_price() -> float:
    """แปลง CRT_MIN_RANGE_POINTS เป็นหน่วยราคา (BTC = 4× ของ XAU)"""
    try:
        info = mt5.symbol_info(SYMBOL)
        point = float(getattr(info, "point", 0.01) or 0.01)
    except Exception:
        point = 0.01
    return float(CRT_MIN_RANGE_POINTS) * point * points_scale()


def crt_sl_buffer_price() -> float:
    """แปลง CRT_SL_BUFFER_POINTS เป็นหน่วยราคา (BTC = 4× ของ XAU)"""
    try:
        info = mt5.symbol_info(SYMBOL)
        point = float(getattr(info, "point", 0.01) or 0.01)
    except Exception:
        point = 0.01
    return float(CRT_SL_BUFFER_POINTS) * point * points_scale()


def save_runtime_state():
    """บันทึก state สำคัญลงไฟล์เพื่อ restore หลัง restart"""
    try:
        from trailing import (
            fvg_order_tickets, pending_order_tf, position_tf, position_sid,
            position_pattern, position_trend_filter, position_zone_meta, position_forward_meta, _entry_state, _trail_state, _s8_fill_sl,
            _focus_frozen_side
        )
        # S10 MTF armed states (per HTF) — กัน restart ตอน armed อยู่
        try:
            from strategy10 import _armed_states as _s10_armed
            s10_armed_serialized = {k: dict(v) for k, v in _s10_armed.items()}
        except Exception:
            s10_armed_serialized = {}

        state = {
            "saved_at": now_bkk().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": SYMBOL,
            "auto_volume": AUTO_VOLUME,
            "active_strategies": active_strategies,
            "scan_interval": SCAN_INTERVAL,
            "entry_candle_mode": ENTRY_CANDLE_MODE,
            "entry_close_reverse_market": ENTRY_CLOSE_REVERSE_MARKET,
            "entry_close_reverse_limit": ENTRY_CLOSE_REVERSE_LIMIT,
            "tg_queue_debug": TG_QUEUE_DEBUG,
            "sltp_audit_debug": SLTP_AUDIT_DEBUG,
            "trade_debug": TRADE_DEBUG,
            "opposite_order_mode": OPPOSITE_ORDER_MODE,
            "limit_guard": LIMIT_GUARD,
            "limit_guard_points": LIMIT_GUARD_POINTS,
            "limit_guard_tf_mode": LIMIT_GUARD_TF_MODE,
            "engulf_min_points": ENGULF_MIN_POINTS,
            "limit_break_cancel": LIMIT_BREAK_CANCEL,
            "limit_break_cancel_tf": LIMIT_BREAK_CANCEL_TF,
            "limit_trend_recheck": LIMIT_TREND_RECHECK,
            "limit_trend_recheck_rounds": LIMIT_TREND_RECHECK_ROUNDS,
            "sl_atr_enabled": SL_ATR_ENABLED,
            "sl_atr_mult": SL_ATR_MULT,
            "pending_rsi_recheck_enabled": PENDING_RSI_RECHECK_ENABLED,
            "pending_rsi_recheck_mode": PENDING_RSI_RECHECK_MODE,
            "pending_rsi_period": PENDING_RSI_PERIOD,
            "pending_rsi_applied_price": PENDING_RSI_APPLIED_PRICE,
            "pending_rsi_buy_max": PENDING_RSI_BUY_MAX,
            "pending_rsi_sell_min": PENDING_RSI_SELL_MIN,
            "trend_filter_scan_block": TREND_FILTER_SCAN_BLOCK,
            "pd_zone_check_enabled": PD_ZONE_CHECK_ENABLED,
            "recheck_combined_mode": RECHECK_COMBINED_MODE,
            "near_approach_cancel_enabled": NEAR_APPROACH_CANCEL_ENABLED,
            "near_approach_cancel_points": NEAR_APPROACH_CANCEL_POINTS,
            "trail_sl_immediate": TRAIL_SL_IMMEDIATE,
            "trail_sl_enabled": TRAIL_SL_ENABLED,
            "trail_sl_reversal_override_enabled": TRAIL_SL_REVERSAL_OVERRIDE_ENABLED,
            "trail_sl_focus_new_enabled": TRAIL_SL_FOCUS_NEW_ENABLED,
            "trail_sl_focus_new_points": TRAIL_SL_FOCUS_NEW_POINTS,
            "trail_sl_focus_new_tf_mode": TRAIL_SL_FOCUS_NEW_TF_MODE,
            "entry_candle_focus_new_enabled": ENTRY_CANDLE_FOCUS_NEW_ENABLED,
            "entry_candle_focus_new_points": ENTRY_CANDLE_FOCUS_NEW_POINTS,
            "entry_candle_focus_new_tf_mode": ENTRY_CANDLE_FOCUS_NEW_TF_MODE,
            "trend_filter_per_tf": TREND_FILTER_PER_TF,
            "trend_filter_higher_tf_enabled": TREND_FILTER_HIGHER_TF_ENABLED,
            "trend_filter_higher_tf": TREND_FILTER_HIGHER_TF,
            "trend_filter_trail_sl_override_enabled": TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED,
            "trend_filter_sideway_hhll": TREND_FILTER_SIDEWAY_HHLL,
            "trend_filter_mode": TREND_FILTER_MODE,
            "swing_summary_mode": SWING_SUMMARY_MODE,
            "swing_pivot_left": SWING_PIVOT_LEFT,
            "swing_pivot_right": SWING_PIVOT_RIGHT,
            "crt_bar_mode": CRT_BAR_MODE,
            "crt_sweep_depth_pct": CRT_SWEEP_DEPTH_PCT,
            "crt_entry_mode": CRT_ENTRY_MODE,
            "s10_armed_states": s10_armed_serialized,
            "rsi9_plot_bullish": RSI9_PLOT_BULLISH,
            "rsi9_plot_hidden_bullish": RSI9_PLOT_HIDDEN_BULLISH,
            "rsi9_plot_bearish": RSI9_PLOT_BEARISH,
            "rsi9_plot_hidden_bearish": RSI9_PLOT_HIDDEN_BEARISH,
            "entry_candle_enabled": ENTRY_CANDLE_ENABLED,
            "opposite_order_enabled": OPPOSITE_ORDER_ENABLED,
            "limit_sweep": LIMIT_SWEEP,
            "delay_sl_mode": DELAY_SL_MODE,
            "fvg_normal": FVG_NORMAL,
            "fvg_parallel": FVG_PARALLEL,
            "sl_guard_enabled": SL_GUARD_ENABLED,
            "sl_guard_count": SL_GUARD_COUNT,
            "sl_guard_near_points": SL_GUARD_NEAR_POINTS,
            "sl_guard_loss_enabled": SL_GUARD_LOSS_ENABLED,
            "sl_guard_loss_threshold": SL_GUARD_LOSS_THRESHOLD,
            "sl_guard_close_on_activate": SL_GUARD_CLOSE_ON_ACTIVATE,
            "sl_guard_combined_enabled": SL_GUARD_COMBINED_ENABLED,
            "sl_guard_combined_count": SL_GUARD_COMBINED_COUNT,
            "sl_guard_combined_tfs": list(SL_GUARD_COMBINED_TFS),
            "sl_guard_group_enabled": SL_GUARD_GROUP_ENABLED,
            "sl_guard_group_count": SL_GUARD_GROUP_COUNT,
            "last_traded_per_tf": last_traded_per_tf,
            "last_traded_sid_tf": last_traded_sid_tf,
            "pending_order_tf": pending_order_tf,
            "position_tf": position_tf,
            "position_sid": position_sid,
            "position_pattern": position_pattern,
            "position_trend_filter": position_trend_filter,
            "position_zone_meta": position_zone_meta,
            "position_forward_meta": position_forward_meta,
            "entry_state": _entry_state,
            "trail_state": _trail_state,
            "fvg_order_tickets": fvg_order_tickets,
            "s8_fill_sl": _s8_fill_sl,
            "trail_sl_frozen_side": _focus_frozen_side.get("trail_sl"),
            "entry_candle_frozen_side": _focus_frozen_side.get("entry_candle"),
            "scale_out_enabled": SCALE_OUT_ENABLED,
            "scale_out_state": {str(k): v for k, v in scale_out_state.items()},
            # S15 Volume Profile POC
            "s15_use_val_vah":  S15_USE_VAL_VAH,
            "s15_lookback":     S15_LOOKBACK,
            "s15_min_rr":       S15_MIN_RR,
        }

        tmp_path = STATE_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, STATE_FILE)
    except Exception as e:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ save_runtime_state error: {e}")


def restore_runtime_state():
    """restore state จากไฟล์ แล้วกรองให้เหลือเฉพาะ ticket ที่ยังมีใน MT5"""
    if not os.path.exists(STATE_FILE):
        return {"restored": False, "reason": "state file not found"}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception as e:
        return {"restored": False, "reason": f"load error: {e}"}

    try:
        from trailing import (
            fvg_order_tickets, pending_order_tf, position_tf, position_sid,
            position_pattern, position_trend_filter, position_zone_meta, position_forward_meta, _entry_state, _trail_state, _s8_fill_sl,
            _focus_frozen_side
        )

        positions = mt5.positions_get(symbol=SYMBOL) or []
        orders = mt5.orders_get(symbol=SYMBOL) or []
        open_pos_tickets = {int(p.ticket) for p in positions}
        open_order_tickets = {int(o.ticket) for o in orders}
        valid_tickets = open_pos_tickets | open_order_tickets

        last_traded_per_tf.clear()
        last_traded_per_tf.update(state.get("last_traded_per_tf", {}))

        last_traded_sid_tf.clear()
        last_traded_sid_tf.update(state.get("last_traded_sid_tf", {}))

        saved_auto_volume = state.get("auto_volume")
        if isinstance(saved_auto_volume, (int, float)) and saved_auto_volume > 0:
            global AUTO_VOLUME
            AUTO_VOLUME = round(float(saved_auto_volume), 2)

        saved_active_strategies = state.get("active_strategies", {})
        if isinstance(saved_active_strategies, dict):
            for sid in active_strategies:
                if sid in saved_active_strategies or str(sid) in saved_active_strategies:
                    active_strategies[sid] = bool(saved_active_strategies.get(sid, saved_active_strategies.get(str(sid))))

        global TG_QUEUE_DEBUG, SLTP_AUDIT_DEBUG, TRADE_DEBUG, OPPOSITE_ORDER_MODE
        global ENTRY_CANDLE_MODE, ENTRY_CLOSE_REVERSE_MARKET, ENTRY_CLOSE_REVERSE_LIMIT
        global LIMIT_GUARD, LIMIT_GUARD_POINTS, LIMIT_GUARD_TF_MODE, ENGULF_MIN_POINTS
        global LIMIT_BREAK_CANCEL, LIMIT_BREAK_CANCEL_TF, LIMIT_TREND_RECHECK, LIMIT_TREND_RECHECK_ROUNDS
        global SL_ATR_ENABLED, SL_ATR_MULT
        global PENDING_RSI_RECHECK_ENABLED, PENDING_RSI_PERIOD
        global PENDING_RSI_APPLIED_PRICE, PENDING_RSI_BUY_MAX, PENDING_RSI_SELL_MIN
        global TREND_FILTER_SCAN_BLOCK
        global NEAR_APPROACH_CANCEL_ENABLED, NEAR_APPROACH_CANCEL_POINTS
        global TRAIL_SL_IMMEDIATE, LIMIT_SWEEP
        global DELAY_SL_MODE
        global FVG_NORMAL, FVG_PARALLEL
        global TRAIL_SL_ENABLED, ENTRY_CANDLE_ENABLED, OPPOSITE_ORDER_ENABLED
        global TRAIL_SL_FOCUS_NEW_ENABLED, TRAIL_SL_FOCUS_NEW_POINTS, TRAIL_SL_FOCUS_NEW_TF_MODE
        global TRAIL_SL_REVERSAL_OVERRIDE_ENABLED
        global ENTRY_CANDLE_FOCUS_NEW_ENABLED, ENTRY_CANDLE_FOCUS_NEW_POINTS, ENTRY_CANDLE_FOCUS_NEW_TF_MODE
        global TREND_FILTER_HIGHER_TF_ENABLED, TREND_FILTER_HIGHER_TF, TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED
        global TREND_FILTER_SIDEWAY_HHLL
        global TREND_FILTER_MODE
        global SWING_SUMMARY_MODE, SWING_PIVOT_LEFT, SWING_PIVOT_RIGHT
        global CRT_BAR_MODE, CRT_SWEEP_DEPTH_PCT, CRT_ENTRY_MODE
        global RSI9_PLOT_BULLISH, RSI9_PLOT_HIDDEN_BULLISH, RSI9_PLOT_BEARISH, RSI9_PLOT_HIDDEN_BEARISH
        TG_QUEUE_DEBUG = bool(state.get("tg_queue_debug", TG_QUEUE_DEBUG))
        SLTP_AUDIT_DEBUG = bool(state.get("sltp_audit_debug", SLTP_AUDIT_DEBUG))
        TRADE_DEBUG = bool(state.get("trade_debug", TRADE_DEBUG))
        saved_entry_mode = state.get("entry_candle_mode")
        if saved_entry_mode in ("close", "classic", "close_percentage"):
            ENTRY_CANDLE_MODE = saved_entry_mode
        ENTRY_CLOSE_REVERSE_MARKET = bool(state.get("entry_close_reverse_market", ENTRY_CLOSE_REVERSE_MARKET))
        ENTRY_CLOSE_REVERSE_LIMIT = bool(state.get("entry_close_reverse_limit", ENTRY_CLOSE_REVERSE_LIMIT))
        saved_opp = state.get("opposite_order_mode")
        if saved_opp in ("tp_close", "sl_protect"):
            OPPOSITE_ORDER_MODE = saved_opp
        LIMIT_GUARD = bool(state.get("limit_guard", LIMIT_GUARD))
        saved_lg_pts = state.get("limit_guard_points")
        if saved_lg_pts is not None:
            LIMIT_GUARD_POINTS = int(saved_lg_pts)
        saved_lg_tf = state.get("limit_guard_tf_mode")
        if saved_lg_tf in ("separate", "combined"):
            LIMIT_GUARD_TF_MODE = saved_lg_tf
        saved_engulf_pts = state.get("engulf_min_points")
        if saved_engulf_pts is not None:
            ENGULF_MIN_POINTS = int(saved_engulf_pts)
        LIMIT_BREAK_CANCEL = bool(state.get("limit_break_cancel", LIMIT_BREAK_CANCEL))
        saved_lbc_tf = state.get("limit_break_cancel_tf", {})
        if isinstance(saved_lbc_tf, dict):
            for tf_name in LIMIT_BREAK_CANCEL_TF:
                if tf_name in saved_lbc_tf:
                    LIMIT_BREAK_CANCEL_TF[tf_name] = bool(saved_lbc_tf[tf_name])
        LIMIT_TREND_RECHECK = bool(state.get("limit_trend_recheck", LIMIT_TREND_RECHECK))
        saved_ltr_rounds = state.get("limit_trend_recheck_rounds")
        if saved_ltr_rounds is not None and int(saved_ltr_rounds) in (1, 2, 3):
            LIMIT_TREND_RECHECK_ROUNDS = int(saved_ltr_rounds)
        SL_ATR_ENABLED = bool(state.get("sl_atr_enabled", SL_ATR_ENABLED))
        saved_sl_atr_mult = state.get("sl_atr_mult")
        if saved_sl_atr_mult is not None and int(saved_sl_atr_mult) in (1, 2, 3, 4, 5):
            SL_ATR_MULT = int(saved_sl_atr_mult)
        PENDING_RSI_RECHECK_ENABLED = bool(state.get("pending_rsi_recheck_enabled", PENDING_RSI_RECHECK_ENABLED))
        saved_rsi_mode = state.get("pending_rsi_recheck_mode")
        if saved_rsi_mode is not None:
            PENDING_RSI_RECHECK_MODE = int(saved_rsi_mode)
        saved_prr_period = state.get("pending_rsi_period")
        if saved_prr_period is not None:
            PENDING_RSI_PERIOD = max(2, int(saved_prr_period))
        saved_prr_applied = state.get("pending_rsi_applied_price")
        if saved_prr_applied in ("open", "high", "low", "close", "median", "hl2", "typical", "hlc3", "weighted", "hlcc4", "weighted_close"):
            PENDING_RSI_APPLIED_PRICE = saved_prr_applied
        saved_prr_buy = state.get("pending_rsi_buy_max")
        if saved_prr_buy is not None:
            PENDING_RSI_BUY_MAX = float(saved_prr_buy)
        saved_prr_sell = state.get("pending_rsi_sell_min")
        if saved_prr_sell is not None:
            PENDING_RSI_SELL_MIN = float(saved_prr_sell)
        TREND_FILTER_SCAN_BLOCK = bool(state.get("trend_filter_scan_block", TREND_FILTER_SCAN_BLOCK))
        PD_ZONE_CHECK_ENABLED = bool(state.get("pd_zone_check_enabled", PD_ZONE_CHECK_ENABLED))
        RECHECK_COMBINED_MODE = bool(state.get("recheck_combined_mode", RECHECK_COMBINED_MODE))
        NEAR_APPROACH_CANCEL_ENABLED = bool(state.get("near_approach_cancel_enabled", NEAR_APPROACH_CANCEL_ENABLED))
        saved_nac_pts = state.get("near_approach_cancel_points")
        if saved_nac_pts is not None:
            NEAR_APPROACH_CANCEL_POINTS = int(saved_nac_pts)
        TRAIL_SL_IMMEDIATE = bool(state.get("trail_sl_immediate", TRAIL_SL_IMMEDIATE))
        TRAIL_SL_ENABLED = bool(state.get("trail_sl_enabled", TRAIL_SL_ENABLED))
        TRAIL_SL_REVERSAL_OVERRIDE_ENABLED = bool(
            state.get("trail_sl_reversal_override_enabled", TRAIL_SL_REVERSAL_OVERRIDE_ENABLED)
        )
        TRAIL_SL_FOCUS_NEW_ENABLED = bool(state.get("trail_sl_focus_new_enabled", TRAIL_SL_FOCUS_NEW_ENABLED))
        saved_tfn_pts = state.get("trail_sl_focus_new_points")
        if isinstance(saved_tfn_pts, (int, float)) and int(saved_tfn_pts) >= 0:
            TRAIL_SL_FOCUS_NEW_POINTS = int(saved_tfn_pts)
        saved_tfn_tfm = state.get("trail_sl_focus_new_tf_mode")
        if saved_tfn_tfm in ("separate", "combined"):
            TRAIL_SL_FOCUS_NEW_TF_MODE = saved_tfn_tfm
        ENTRY_CANDLE_FOCUS_NEW_ENABLED = bool(state.get("entry_candle_focus_new_enabled", ENTRY_CANDLE_FOCUS_NEW_ENABLED))
        saved_efn_pts = state.get("entry_candle_focus_new_points")
        if isinstance(saved_efn_pts, (int, float)) and int(saved_efn_pts) >= 0:
            ENTRY_CANDLE_FOCUS_NEW_POINTS = int(saved_efn_pts)
        saved_efn_tfm = state.get("entry_candle_focus_new_tf_mode")
        if saved_efn_tfm in ("separate", "combined"):
            ENTRY_CANDLE_FOCUS_NEW_TF_MODE = saved_efn_tfm
        saved_tf_ptf = state.get("trend_filter_per_tf", {})
        if isinstance(saved_tf_ptf, dict):
            for tf_name in TREND_FILTER_PER_TF:
                if tf_name in saved_tf_ptf:
                    TREND_FILTER_PER_TF[tf_name] = bool(saved_tf_ptf[tf_name])
        TREND_FILTER_HIGHER_TF_ENABLED = bool(state.get("trend_filter_higher_tf_enabled", TREND_FILTER_HIGHER_TF_ENABLED))
        saved_tf_ht = state.get("trend_filter_higher_tf")
        if saved_tf_ht in TF_OPTIONS:
            TREND_FILTER_HIGHER_TF = saved_tf_ht
        TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED = bool(
            state.get("trend_filter_trail_sl_override_enabled", TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED)
        )
        TREND_FILTER_SIDEWAY_HHLL = bool(
            state.get("trend_filter_sideway_hhll", TREND_FILTER_SIDEWAY_HHLL)
        )
        saved_tf_mode = state.get("trend_filter_mode")
        if saved_tf_mode in ("basic", "breakout"):
            TREND_FILTER_MODE = saved_tf_mode
        saved_swing_mode = state.get("swing_summary_mode")
        if saved_swing_mode in ("pair", "pivot"):
            SWING_SUMMARY_MODE = saved_swing_mode
        try:
            saved_swing_left = int(state.get("swing_pivot_left", SWING_PIVOT_LEFT))
            if saved_swing_left >= 1:
                SWING_PIVOT_LEFT = saved_swing_left
        except Exception:
            pass
        try:
            saved_swing_right = int(state.get("swing_pivot_right", SWING_PIVOT_RIGHT))
            if saved_swing_right >= 1:
                SWING_PIVOT_RIGHT = saved_swing_right
        except Exception:
            pass
        saved_crt_mode = state.get("crt_bar_mode")
        if saved_crt_mode in ("2bar", "3bar"):
            CRT_BAR_MODE = saved_crt_mode
        try:
            saved_crt_pct = float(state.get("crt_sweep_depth_pct", CRT_SWEEP_DEPTH_PCT))
            if 0.0 <= saved_crt_pct <= 1.0:
                CRT_SWEEP_DEPTH_PCT = saved_crt_pct
        except Exception:
            pass
        saved_crt_entry = state.get("crt_entry_mode")
        if saved_crt_entry in ("htf", "mtf"):
            CRT_ENTRY_MODE = saved_crt_entry
        # S10 MTF armed states — restore in-place เพื่อให้ strategy10 module เห็นข้อมูลเดียวกัน
        # NOTE: skip arm ที่เก่าเกินไป (armed_at + 2 HTF bars < now) เพื่อกัน stale state
        # หลัง bot restart ที่อาจถือ parent candle เก่าหลายวัน
        try:
            from strategy10 import _armed_states as _s10_armed, _TF_SECONDS as _s10_tf_secs
            import time as _t
            _s10_armed.clear()
            saved_s10_armed = state.get("s10_armed_states", {})
            _now_unix = int(_t.time())
            if isinstance(saved_s10_armed, dict):
                for htf_tf, st in saved_s10_armed.items():
                    if not (isinstance(st, dict) and st.get("direction") in ("BUY", "SELL")):
                        continue
                    # ตรวจความสดของ arm — armed_at + 2 HTF bars ต้องยังไม่ผ่าน
                    _armed_at  = int(st.get("armed_at", 0) or 0)
                    _htf_secs  = _s10_tf_secs.get(htf_tf, 3600)
                    if _armed_at > 0 and (_armed_at + 2 * _htf_secs) < _now_unix:
                        # arm นี้หมดอายุไปแล้ว — ไม่ต้อง restore
                        continue
                    _s10_armed[htf_tf] = dict(st)
        except Exception:
            pass
        RSI9_PLOT_BULLISH = bool(state.get("rsi9_plot_bullish", RSI9_PLOT_BULLISH))
        RSI9_PLOT_HIDDEN_BULLISH = bool(state.get("rsi9_plot_hidden_bullish", RSI9_PLOT_HIDDEN_BULLISH))
        RSI9_PLOT_BEARISH = bool(state.get("rsi9_plot_bearish", RSI9_PLOT_BEARISH))
        RSI9_PLOT_HIDDEN_BEARISH = bool(state.get("rsi9_plot_hidden_bearish", RSI9_PLOT_HIDDEN_BEARISH))
        ENTRY_CANDLE_ENABLED = bool(state.get("entry_candle_enabled", ENTRY_CANDLE_ENABLED))
        OPPOSITE_ORDER_ENABLED = bool(state.get("opposite_order_enabled", OPPOSITE_ORDER_ENABLED))
        LIMIT_SWEEP = bool(state.get("limit_sweep", LIMIT_SWEEP))
        global SCALE_OUT_ENABLED
        SCALE_OUT_ENABLED = bool(state.get("scale_out_enabled", SCALE_OUT_ENABLED))
        # Restore TSO state (เฉพาะ ticket ที่ยังมีจริงใน MT5)
        scale_out_state.clear()
        saved_so_state = state.get("scale_out_state", {})
        if isinstance(saved_so_state, dict):
            for k, v in saved_so_state.items():
                try:
                    tk = int(k)
                except (TypeError, ValueError):
                    continue
                if tk in valid_tickets and isinstance(v, dict):
                    scale_out_state[tk] = v
        saved_delay_sl = state.get("delay_sl_mode")
        if saved_delay_sl in ("off", "time", "price"):
            DELAY_SL_MODE = saved_delay_sl
        FVG_NORMAL = bool(state.get("fvg_normal", FVG_NORMAL))
        FVG_PARALLEL = bool(state.get("fvg_parallel", FVG_PARALLEL))

        global SL_GUARD_ENABLED, SL_GUARD_COUNT, SL_GUARD_NEAR_POINTS
        global SL_GUARD_LOSS_ENABLED, SL_GUARD_LOSS_THRESHOLD, SL_GUARD_CLOSE_ON_ACTIVATE
        global SL_GUARD_COMBINED_ENABLED, SL_GUARD_COMBINED_COUNT, SL_GUARD_COMBINED_TFS
        global SL_GUARD_GROUP_ENABLED, SL_GUARD_GROUP_COUNT
        SL_GUARD_ENABLED = bool(state.get("sl_guard_enabled", SL_GUARD_ENABLED))
        saved_sg_cnt = state.get("sl_guard_count")
        if saved_sg_cnt is not None:
            SL_GUARD_COUNT = max(1, int(saved_sg_cnt))
        saved_sg_pts = state.get("sl_guard_near_points")
        if saved_sg_pts is not None:
            SL_GUARD_NEAR_POINTS = max(0, int(saved_sg_pts))
        SL_GUARD_LOSS_ENABLED = bool(state.get("sl_guard_loss_enabled", SL_GUARD_LOSS_ENABLED))
        saved_sg_loss_thr = state.get("sl_guard_loss_threshold")
        if saved_sg_loss_thr is not None:
            SL_GUARD_LOSS_THRESHOLD = max(0.0, float(saved_sg_loss_thr))
        SL_GUARD_CLOSE_ON_ACTIVATE = bool(state.get("sl_guard_close_on_activate", SL_GUARD_CLOSE_ON_ACTIVATE))
        SL_GUARD_COMBINED_ENABLED = bool(state.get("sl_guard_combined_enabled", SL_GUARD_COMBINED_ENABLED))
        saved_sgc_cnt = state.get("sl_guard_combined_count")
        if saved_sgc_cnt is not None:
            SL_GUARD_COMBINED_COUNT = max(1, int(saved_sgc_cnt))
        saved_sgc_tfs = state.get("sl_guard_combined_tfs")
        if isinstance(saved_sgc_tfs, list):
            SL_GUARD_COMBINED_TFS = [t for t in saved_sgc_tfs if t in TF_OPTIONS]
        SL_GUARD_GROUP_ENABLED = bool(state.get("sl_guard_group_enabled", SL_GUARD_GROUP_ENABLED))
        saved_sgg_cnt = state.get("sl_guard_group_count")
        if saved_sgg_cnt is not None:
            SL_GUARD_GROUP_COUNT = max(1, int(saved_sgg_cnt))

        global S15_USE_VAL_VAH, S15_LOOKBACK, S15_MIN_RR
        S15_USE_VAL_VAH = bool(state.get("s15_use_val_vah", S15_USE_VAL_VAH))
        saved_s15_lb = state.get("s15_lookback")
        if saved_s15_lb is not None:
            S15_LOOKBACK = max(30, int(saved_s15_lb))
        saved_s15_rr = state.get("s15_min_rr")
        if saved_s15_rr is not None:
            S15_MIN_RR = max(0.5, float(saved_s15_rr))

        pending_order_tf.clear()
        pending_order_tf.update({
            t: v for t, v in _int_key_dict(state.get("pending_order_tf", {})).items()
            if t in open_order_tickets
        })

        position_tf.clear()
        position_tf.update({
            t: v for t, v in _int_key_dict(state.get("position_tf", {})).items()
            if t in valid_tickets
        })

        position_sid.clear()
        position_sid.update({
            t: v for t, v in _int_key_dict(state.get("position_sid", {})).items()
            if t in valid_tickets
        })

        position_pattern.clear()
        position_pattern.update({
            t: v for t, v in _int_key_dict(state.get("position_pattern", {})).items()
            if t in valid_tickets
        })

        position_trend_filter.clear()
        position_trend_filter.update({
            t: v for t, v in _int_key_dict(state.get("position_trend_filter", {})).items()
            if t in valid_tickets
        })

        position_zone_meta.clear()
        position_zone_meta.update({
            t: v for t, v in _int_key_dict(state.get("position_zone_meta", {})).items()
            if t in valid_tickets
        })

        position_forward_meta.clear()
        position_forward_meta.update({
            t: v for t, v in _int_key_dict(state.get("position_forward_meta", {})).items()
            if t in valid_tickets
        })

        _entry_state.clear()
        _entry_state.update({
            t: v for t, v in _int_key_dict(state.get("entry_state", {})).items()
            if t in open_pos_tickets
        })

        _trail_state.clear()
        _trail_state.update({
            t: v for t, v in _int_key_dict(state.get("trail_state", {})).items()
            if t in open_pos_tickets
        })

        fvg_order_tickets.clear()
        fvg_order_tickets.update({
            t: v for t, v in _int_key_dict(state.get("fvg_order_tickets", {})).items()
            if t in valid_tickets
        })

        _s8_fill_sl.clear()
        _s8_fill_sl.update({
            t: float(v) for t, v in _int_key_dict(state.get("s8_fill_sl", {})).items()
            if t in valid_tickets
        })

        for feature_key, state_key in (
            ("trail_sl", "trail_sl_frozen_side"),
            ("entry_candle", "entry_candle_frozen_side"),
        ):
            saved_side = state.get(state_key)
            _focus_frozen_side[feature_key] = saved_side if saved_side in ("BUY", "SELL") else None

        return {
            "restored": True,
            "saved_at": state.get("saved_at", ""),
            "positions": len(open_pos_tickets),
            "orders": len(open_order_tickets),
            "pending_order_tf": len(pending_order_tf),
            "position_tf": len(position_tf),
            "entry_state": len(_entry_state),
            "trail_state": len(_trail_state),
        }
    except Exception as e:
        return {"restored": False, "reason": f"restore error: {e}"}
last_traded_candle = 0   # backward compat

def should_log_tf(tf_name: str, scan_interval: int) -> bool:
    """
    Log เฉพาะ TF ที่ครบรอบเวลา ณ ขณะนี้
    scan 1 นาที → log ทุก TF ที่ minute % tf_minutes == 0
    เช่น scan=1 → log M1 ทุกนาที
         scan=5 → log M1,M5 ทุก 5 นาที
         scan=15 → log M1,M5,M15 ทุก 15 นาที
    """
    tf_min = TF_MINUTES.get(tf_name, 1)
    now_min = datetime.now().minute
    now_hour = datetime.now().hour
    total_min = now_hour * 60 + now_min

    # TF ที่มีค่าน้อยกว่าหรือเท่ากับ scan_interval → log ทุก scan
    if tf_min <= scan_interval:
        return True
    # TF ที่ใหญ่กว่า → log เมื่อครบรอบ
    return total_min % tf_min == 0

async def scan_one_tf(app, tf_name: str) -> bool:
    """สแกน 1 Timeframe — return True ถ้าเปิด Order สำเร็จ"""
    tf_val = TF_OPTIONS[tf_name]
    now    = now_bkk().strftime("%H:%M:%S")

    lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)

    # ดึงแท่งที่ปิดแล้วแน่ๆ
    # start=1 = ข้ามแท่งที่กำลังวิ่งอยู่ (index 0)
    # แท่ง[-1] ของ rates = แท่งที่เพิ่งปิดล่าสุด = แท่ง[0] ใน Strategy
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback + 6)
    if rates is None or len(rates) < lookback + 4:
        return False

    last_candle_time = int(rates[-1]["time"])

    # ตรวจซ้ำว่าแท่ง[-1] ปิดจริงแล้ว
    # โดยเทียบกับแท่งปัจจุบัน (index=0) — ถ้า time ตรงกันแปลว่ายังวิ่งอยู่
    current_bar = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 1)
    if current_bar is not None and len(current_bar) > 0:
        if int(current_bar[0]["time"]) == last_candle_time:
            print(f"⏳ [{now}] {tf_name}: รอแท่ง[0] ปิด...")
            return False
        # ตรวจเพิ่มเติม: แท่ง[-1] ต้องเป็นแท่งก่อนหน้าแท่งปัจจุบัน
        # นั่นคือ last_candle_time < current_bar[0]["time"]
        if last_candle_time >= int(current_bar[0]["time"]):
            print(f"⏳ [{now}] {tf_name}: แท่ง[0] ยังไม่ปิดสมบูรณ์")
            return False

    # กัน Order ซ้ำในแท่งเดิมของ TF นี้
    if last_traded_per_tf.get(tf_name) == last_candle_time:
        print(f"⏭️ [{now}] {tf_name}: เทรดแท่งนี้ไปแล้ว")
        return False

    # วิเคราะห์ Strategy — S1 และ S2 ทำงานพร้อมกันอิสระ
    # รัน S1 และ S2 แยกกัน แล้วค่อย merge ผล
    r1 = strategy_1(rates) if active_strategies.get(1, False) else {"signal": "WAIT", "reason": "S1 ปิด"}
    r2 = strategy_2(rates) if active_strategies.get(2, False) else {"signal": "WAIT", "reason": "S2 ปิด"}

    # ── จัดการ FVG (S2) ก่อน — register pending แม้ S1 ได้สัญญาณ ──
    if r2.get("signal") == "FVG_DETECTED":
        fvg    = r2["fvg"]
        fvg_key = f"{tf_name}_{last_candle_time}"
        if fvg_key not in fvg_pending and last_traded_per_tf.get(tf_name) != last_candle_time:
            tp_swing = find_swing_tp(rates, fvg["signal"], fvg["entry"], fvg["sl"])
            tp = tp_swing if tp_swing else round(
                fvg["entry"] + abs(fvg["entry"] - fvg["sl"]) if fvg["signal"] == "BUY"
                else fvg["entry"] - abs(fvg["sl"] - fvg["entry"]), 2
            )
            tp_note = ("Swing High:" + str(tp)) if (tp_swing and fvg["signal"] == "BUY") else \
                      ("Swing Low:" + str(tp)) if tp_swing else "RR1:1 (fallback)"
            fvg_pending[fvg_key] = {
                "tf": tf_name, "signal": fvg["signal"],
                "entry": fvg["entry"], "sl": fvg["sl"], "tp": tp,
                "tp_note": tp_note, "gap_top": fvg["gap_top"],
                "gap_bot": fvg["gap_bot"], "c3_type": fvg.get("c3_type", ""),
                "candle_key": last_candle_time,
            }
            sig_e = "🟢" if fvg["signal"] == "BUY" else "🔴"
            msg_fvg = (
                f"{sig_e} *FVG {fvg['signal']} ตรวจพบ! [{tf_name}]*\n"
                f"Gap: `{fvg['gap_bot']}` – `{fvg['gap_top']}`\n"
                f"แท่ง[3]: {fvg.get('c3_type','')}\n"
                f"📌 Entry 98%: `{fvg['entry']}`\n"
                f"🛑 SL: `{fvg['sl']}` | 🎯 TP: `{tp}`\n"
                f"({tp_note})\n"
                f"\n⏳ รอราคาย้อนมาแตะ Entry..."
            )
            await app.bot.send_message(chat_id=MY_USER_ID, text=msg_fvg, parse_mode="Markdown")
            print(f"📋 [{now}] {tf_name}: บันทึก FVG รอราคาแตะ Entry={fvg['entry']}")

    # ── เลือก result สำหรับ S1 ──
    # S1 ได้สัญญาณจริง → execute S1
    # S1 WAIT → return (S2 จัดการแล้วด้านบน)
    if r1.get("signal") not in ("WAIT",):
        result = r1
    else:
        return False  # ไม่มีสัญญาณ S1

    signal  = result.get("signal", "WAIT")
    pattern = result.get("pattern", "")
    if should_log_tf(tf_name, SCAN_INTERVAL):
        print(f"🔍 [{now}] {tf_name}: {signal} — {result.get('reason','')[:50]}")

    if signal == "WAIT":
        return False

    # Pattern B วิธี 2: บันทึกไว้ใน pb_pending เพื่อรอราคาแตะ 50% Body[1]
    # (Bot จะตรวจ real-time ทุก scan cycle แม้แท่ง[0] ยังไม่ปิด)
    if "Pattern B" in pattern:
        entry     = result["entry"]
        pb_key    = f"{tf_name}_{last_candle_time}"
        if pb_key not in pb_pending and last_traded_per_tf.get(tf_name) != last_candle_time:
            pb_pending[pb_key] = {
                "tf":         tf_name,
                "signal":     signal,
                "entry":      entry,
                "sl":         result["sl"],
                "tp":         result["tp"],
                "candle_key": last_candle_time,
            }
            print(f"📋 [{now}] {tf_name}: บันทึก Pattern B วิธี 2 ที่ Entry={entry}")

    sig_e  = "🟢" if signal == "BUY" else "🔴"
    entry  = result["entry"]
    sl     = result["sl"]
    tp     = result["tp"]
    risk   = abs(entry - sl)
    rr     = round(abs(tp - entry) / risk, 2) if risk > 0 else 0

    # สร้างข้อมูลแท่งเทียน
    candle_txt = ""
    labels = ["[3]", "[2]", "[1]", "[0]"]
    for i, c in enumerate(result.get("candles", [])):
        o, h, l, cl = float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"])
        color = "🟢" if cl > o else "🔴"
        candle_txt += f"{color} แท่ง{labels[i]}: O:`{o:.2f}` H:`{h:.2f}` L:`{l:.2f}` C:`{cl:.2f}`\n"

    tick          = mt5.symbol_info_tick(SYMBOL)
    current_price = (tick.ask if signal == "BUY" else tick.bid) if tick else 0
    price_diff    = round(abs(current_price - entry), 2)

    await app.bot.send_message(
        chat_id=MY_USER_ID,
        text=(
            f"{sig_e} *{result['pattern']}*\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🕐 {now_bkk().strftime('%d/%m/%Y %H:%M')}\n"
            f"📊 *Timeframe: {tf_name}*\n\n"
            f"{candle_txt}\n"
            f"📈 Swing High:`{result['swing_high']:.2f}` | Low:`{result['swing_low']:.2f}`\n\n"
            f"💬 *เหตุผลที่เข้าเงื่อนไข:*\n{result['reason']}\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"💰 ราคาปัจจุบัน: `{current_price:.2f}`\n"
            f"📌 *Limit ที่:* `{entry}` (ห่าง {price_diff})\n"
            f"🛑 SL: `{sl}` | 🎯 TP: `{tp}`\n"
            f"⚖️ R:R `1:{rr}` | 📦 `{AUTO_VOLUME}` lot\n\n"
            f"⏳ กำลังตั้ง Limit Order..."
        ),
        parse_mode="Markdown"
    )

    # ตรวจสอบอีกครั้งก่อนตั้ง Order ว่า Swing ยังไม่ถูกกลืน
    # ตรวจว่าควรยกเลิก (ราคาผ่านไป หรือกลืนกิน Swing ย่อย)
    cancel, cancel_reason = should_cancel_pending(rates, signal, entry)
    if cancel:
        print(f"🚫 [{now}] {tf_name}: {cancel_reason[:60]}")
        await app.bot.send_message(
            chat_id=MY_USER_ID,
            text=f"🚫 *[{tf_name}] ยกเลิก — ไม่ตั้ง Limit*\n{cancel_reason}",
            parse_mode="Markdown"
        )
        return False

    # ── TP เดียวกัน: ถ้ามี Position เปิดอยู่แล้ว ใช้ TP ของ Position นั้น ──
    existing_tp = get_existing_tp(signal, entry, tf_name, requester_sid=1)
    if existing_tp > 0:
        old_tp = tp
        tp = existing_tp
        print(f"📌 [{now}] ใช้ TP เดียวกับ Order แรก: {tp} (เดิม: {old_tp})")

    order = open_order(signal, get_volume(), sl, tp, entry_price=entry, tf=tf_name, sid=1)
    if order["success"]:
        last_traded_per_tf[tf_name] = last_candle_time
        if order.get("ticket"):
            from trailing import position_pattern as _pos_pat
            _pos_pat[order["ticket"]] = result.get("pattern", "")
        ot_name = order.get("order_type", "LIMIT")
        await app.bot.send_message(
            chat_id=MY_USER_ID,
            text=(
                f"✅ *ตั้ง {ot_name} สำเร็จ!*\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"{sig_e} {ot_name} {SYMBOL} [{tf_name}]\n"
                f"📌 Entry รอที่: `{order['price']}`\n"
                f"🛑 SL: `{sl}` | 🎯 TP: `{tp}`\n"
                f"🔖 Ticket: `{order['ticket']}`\n\n"
                f"⏳ รอราคามาแตะ Entry ครับ"
            ),
            parse_mode="Markdown"
        )
        return True
    elif order.get("skipped"):
        print(f"⏭️ [{now}] {tf_name}: {order['error'][:60]}")
        return False
    else:
        await app.bot.send_message(
            chat_id=MY_USER_ID,
            text=f"❌ [{tf_name}] Limit ไม่สำเร็จ: `{order['error']}`",
            parse_mode="Markdown"
        )
        return False


async def check_engulf_trail_sl(app):
    """
    Trailing SL ด้วย Engulfing candle:
    BUY position: ถ้าแท่งล่าสุด (หลัง order เข้าแล้ว ≥1 แท่ง) ปิดเขียว
                  และกลืนกินแท่งก่อนหน้า (Close > High[prev])
                  → ขยับ SL = Low[engulf] - 100 จุด (ถ้า SL ใหม่ > SL เดิม)

    SELL position: ถ้าแท่งล่าสุดปิดแดง และกลืนกิน (Close < Low[prev])
                  → ขยับ SL = High[engulf] + 100 จุด (ถ้า SL ใหม่ < SL เดิม)
    """
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        return

    now = now_bkk().strftime("%H:%M:%S")

    for pos in positions:
        try:
            pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"

            # ดึงแท่งเทียนล่าสุด 3 แท่ง (TF M1 — แท่งที่เปลี่ยนเร็วสุด)
            # ใช้ TF เดียวกับที่ scan หรือ M1 เป็น default
            rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, 4)
            if rates is None or len(rates) < 3:
                continue

            # แท่งล่าสุดที่ปิดแล้ว = rates[-2] (rates[-1] คือแท่งปัจจุบันที่ยังวิ่ง)
            cur  = rates[-2]   # แท่งล่าสุดที่ปิด
            prev = rates[-3]   # แท่งก่อนหน้า

            cur_o  = float(cur["open"]);  cur_h  = float(cur["high"])
            cur_l  = float(cur["low"]);   cur_c  = float(cur["close"])
            prev_h = float(prev["high"]); prev_l = float(prev["low"])
            bull_cur = cur_c > cur_o   # เขียว
            bear_cur = cur_c < cur_o   # แดง

            # ตรวจว่า position เพิ่งเข้า ≥1 แท่ง
            # เวลา open ของ position (unix) vs เวลา open ของแท่ง prev
            pos_open_time = pos.time  # unix timestamp
            bar_open_time = int(prev["time"])
            if pos_open_time >= bar_open_time:
                continue  # position ยังไม่ผ่านแท่งแรก

            new_sl = 0.0

            if pos_type == "BUY" and bull_cur:
                # กลืนกิน: Close > High[prev]
                if cur_c > prev_h:
                    candidate_sl = round(cur_l - 1.0, 2)   # Low[engulf] - 100 จุด (1.0 = 100pt XAUUSD)
                    if candidate_sl > pos.sl:               # ขยับขึ้นเท่านั้น
                        new_sl = candidate_sl

            elif pos_type == "SELL" and bear_cur:
                # กลืนกิน: Close < Low[prev]
                if cur_c < prev_l:
                    candidate_sl = round(cur_h + 1.0, 2)   # High[engulf] + 100 จุด
                    if pos.sl == 0 or candidate_sl < pos.sl:  # ขยับลงเท่านั้น
                        new_sl = candidate_sl

            if new_sl > 0:
                # Modify SL
                result = mt5.order_send({
                    "action":   mt5.TRADE_ACTION_SLTP,
                    "symbol":   SYMBOL,
                    "position": pos.ticket,
                    "sl":       new_sl,
                    "tp":       pos.tp,
                })
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    sig_e = "🟢" if pos_type == "BUY" else "🔴"
                    msg = (
                        f"📐 *Trail SL \u2014 Engulf {pos_type}*\n"
                        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
                        f"{sig_e} Ticket: `{pos.ticket}`\n"
                        f"\U0001f56f Engulf: Low=`{cur_l}` High=`{cur_h}` Close=`{cur_c}`\n"
                        f"\U0001f6d1 SL \u0e40\u0e14\u0e34\u0e21: `{pos.sl}` \u2192 \u0e43\u0e2b\u0e21\u0e48: `{new_sl}`\n"
                        f"\U0001f3af TP: `{pos.tp}`"
                    )
                    await app.bot.send_message(
                        chat_id=MY_USER_ID, text=msg, parse_mode="Markdown"
                    )
                    print(f"📐 [{now}] Trail SL {pos_type} ticket={pos.ticket} SL: {pos.sl}→{new_sl}")
                else:
                    err = result.retcode if result else "no result"
                    print(f"⚠️ [{now}] Trail SL failed: {err}")
        except Exception as e:
            print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ check_engulf_trail_sl error: {e}")


async def auto_scan(app):
    """สแกนทุก Timeframe ที่เปิดอยู่พร้อมกัน"""
    global auto_active
    if not auto_active:
        return
    if not connect_mt5():
        await app.bot.send_message(chat_id=MY_USER_ID, text="⚠️ MT5 ไม่ได้เชื่อมต่อ")
        return

    # ตรวจ SL/TP hit แจ้งเตือน
    await check_sl_tp_hits(app)

    # Trail SL ด้วย Engulfing candle
    await check_engulf_trail_sl(app)

    # ตรวจ FVG และ Pattern B real-time
    await check_fvg_pending(app)
    await check_pb_pending(app)

    positions  = mt5.positions_get(symbol=SYMBOL)
    open_count = len(positions) if positions else 0
    if open_count >= MAX_ORDERS:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ Order เต็ม {open_count}/{MAX_ORDERS}")
        return

    active_tfs = [tf for tf, on in TF_ACTIVE.items() if on]
    if not active_tfs:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ ไม่มี Timeframe ที่เปิดอยู่")
        return

    now = now_bkk().strftime("%H:%M:%S")
    # แสดง log ว่ากำลังสแกน TF อะไรบ้าง
    # รอบแรก → log ทุก TF, รอบถัดไป → filter ตาม interval
    global _first_scan_done
    if not _first_scan_done:
        print(f"🚀 [{now}] Auto Scan เริ่ม! TF ที่เลือก: {', '.join(active_tfs)}")
        print(f"   Strategy: {[STRATEGY_NAMES[k] for k,v in active_strategies.items() if v]}")
        print(f"   Scan Interval: {SCAN_INTERVAL} นาที")
        _first_scan_done = True
        log_tfs = active_tfs   # log ทุก TF รอบแรก
    else:
        log_tfs = [tf for tf in active_tfs if should_log_tf(tf, SCAN_INTERVAL)]
    if log_tfs:
        print(f"🔍 [{now}] สแกน TF: {', '.join(log_tfs)}")

    for tf_name in active_tfs:
        positions  = mt5.positions_get(symbol=SYMBOL)
        open_count = len(positions) if positions else 0
        if open_count >= MAX_ORDERS:
            print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ Order เต็ม — หยุดสแกน")
            break
        await scan_one_tf(app, tf_name)


# ============================================================
#  UI
# ============================================================


def auth(update):
    return update.effective_user.id == MY_USER_ID


async def alert_intruder(update):
    user = update.effective_user
    name = user.full_name or "ไม่ทราบชื่อ"
    un   = f"@{user.username}" if user.username else "ไม่มี"
    print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ คนแปลกหน้า ID:{user.id} | {name} | {un}")
    await update.get_bot().send_message(
        chat_id=MY_USER_ID,
        text=f"🚨 *มีคนพยายามใช้ Bot!*\n👤 {name} | {un}\n🆔 `{user.id}`",
        parse_mode='Markdown'
    )
