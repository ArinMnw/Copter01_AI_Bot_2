import mt5_worker as mt5
import asyncio
import copy
import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def _profile_dir_candidates(profile: str) -> list[str]:
    if not profile:
        return []
    return [
        os.path.join(ROOT_DIR, "profiles", profile),
        os.path.join(ROOT_DIR, "profiles", "demo", profile),
        os.path.join(ROOT_DIR, "profiles", "real", profile),
        os.path.join(ROOT_DIR, "profiles", "demo", "accounts", profile),
        os.path.join(ROOT_DIR, "profiles", "real", "accounts", profile),
    ]


def _resolve_profile_dir(profile: str) -> str:
    for path in _profile_dir_candidates(profile):
        if os.path.exists(os.path.join(path, "profile.env")):
            return path
    return os.path.join(ROOT_DIR, "profiles", profile) if profile else ROOT_DIR


def _load_profile_env() -> None:
    """Load the active BOT_PROFILE profile.env before config constants are read."""
    profile = (os.getenv("BOT_PROFILE") or "").strip()
    if not profile:
        return
    profile_env = os.getenv("BOT_PROFILE_ENV")
    if not profile_env:
        profile_env = os.path.join(_resolve_profile_dir(profile), "profile.env")
    if not os.path.exists(profile_env):
        return
    try:
        with open(profile_env, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)
    except OSError:
        pass


_load_profile_env()

BOT_PROFILE = (os.getenv("BOT_PROFILE") or "").strip()
PROFILE_DIR = _resolve_profile_dir(BOT_PROFILE) if BOT_PROFILE else ROOT_DIR
PROFILE_ACTIVE = bool(BOT_PROFILE)
LOG_DIR = os.path.join(PROFILE_DIR, "logs") if PROFILE_ACTIVE else "logs"
OLD_LOG_DIR = os.path.join(LOG_DIR, "old_logs")
SYSTEM_LOG_DIR = os.path.join(LOG_DIR, "system")
DEBUG_LOG_DIR = os.path.join(LOG_DIR, "debug")
STATE_FILE = os.path.join(PROFILE_DIR, "bot_state.json") if PROFILE_ACTIVE else "bot_state.json"
HEARTBEAT_FILE = os.path.join(PROFILE_DIR, "bot_heartbeat.txt") if PROFILE_ACTIVE else "bot_heartbeat.txt"
SUPERVISOR_LOCK_FILE = os.path.join(PROFILE_DIR, "supervisor.lock") if PROFILE_ACTIVE else "supervisor.lock"
MT5_SERVER_TZ_HISTORY_FILE = (
    os.path.join(PROFILE_DIR, "mt5_server_tz_history.json")
    if PROFILE_ACTIVE
    else os.path.join(ROOT_DIR, "mt5_server_tz_history.json")
)


def _ensure_profile_dirs() -> None:
    for path in (PROFILE_DIR, LOG_DIR, OLD_LOG_DIR, SYSTEM_LOG_DIR, DEBUG_LOG_DIR):
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            pass


_ensure_profile_dirs()

# console บางเครื่อง (เช่น cmd.exe ที่ codepage ไทย cp874) เจอ emoji ใน print()
# แล้ว UnicodeEncodeError ตั้งแต่ import-time ทำให้ main.py ไม่ขึ้นเลย (เคสจริง:
# โหลด optimized_params.json แล้ว print "✅ Loaded..." พังตั้งแต่ก่อนสแกนแม้แต่ครั้งแรก)
# reconfigure ให้ stdout/stderr เป็น UTF-8 เสมอ กันพังจาก emoji/ตัวอักษรไทยทุกที่ในไฟล์นี้
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ── Timezone offset สำหรับ display (Bangkok UTC+7) ──────────
# ถ้าเครื่อง Windows ตั้ง timezone ผิด ให้ปรับ TZ_OFFSET
TZ_OFFSET = 7   # UTC+7 Bangkok
MT5_SERVER_TZ = 1  # ค่าเริ่มต้นก่อน auto-refresh (ดู _refresh_mt5_server_tz ด้านล่าง) —
                    # broker server time เปลี่ยนตาม DST ปีละ 2 ครั้ง hardcode ตรงๆ
                    # ทำให้เลขนี้ผิดไปครึ่งปี (ทุกจุดที่อ่าน config.MT5_SERVER_TZ ตรงๆ
                    # เช่น trailing.py/scanner.py/handlers/* จะแปลง bar time ผิดตามไปด้วย)

_mt5_server_tz_checked_at = 0.0
_MT5_SERVER_TZ_REFRESH_SEC = 300.0  # DST เปลี่ยนปีละ 2 ครั้ง ไม่ต้อง refresh ถี่
_mt5_server_tz_pending: int | None = None   # ค่า offset ใหม่ที่กำลังรอยืนยัน (ยังไม่ commit)
_mt5_server_tz_pending_count = 0
_MT5_SERVER_TZ_CONFIRM_COUNT = 2  # ต้องเห็นค่าใหม่ติดกันกี่ครั้งก่อน commit จริง

# ── MT5_SERVER_TZ history (แยกตามวันที่) ───────────────────────
# MT5_SERVER_TZ ตัวแปร global เก็บได้แค่ "ค่าปัจจุบัน" ค่าเดียว ถ้า broker เปลี่ยน
# server tz (DST) ไปแล้ว ใครเอา MT5_SERVER_TZ ของวันนี้ไปแปลง timestamp ของวันก่อน
# จะเพี้ยนไปตามส่วนต่าง (เคสจริง: ticket 550753658 วันที่ 24/06 ค่าจริงคือ 0 แต่
# วันที่ 25/06 ขยับเป็น 1 → ใครแปลงเวลา deal ของ 24/06 ด้วยค่าวันนี้ จะช้าไป 1h)
# เก็บ history ไว้แยกตามวันที่ (UTC date) เพื่อให้ฟังก์ชันแสดงผล deal/order เก่า
# (เช่น Deal History footer, candle block ของ ticket lookup) ดึงค่าของ "วันนั้น" ได้ถูก
_MT5_SERVER_TZ_HISTORY_FILE = MT5_SERVER_TZ_HISTORY_FILE


def _load_mt5_server_tz_history() -> dict:
    try:
        with open(_MT5_SERVER_TZ_HISTORY_FILE, "r", encoding="utf-8") as f:
            return {str(k): int(v) for k, v in json.load(f).items()}
    except Exception:
        return {}


def _save_mt5_server_tz_history() -> None:
    try:
        with open(_MT5_SERVER_TZ_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(_MT5_SERVER_TZ_HISTORY, f, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception:
        pass


_MT5_SERVER_TZ_HISTORY: dict = _load_mt5_server_tz_history()


def _refresh_mt5_server_tz(tick_ts: int, now_ts: float) -> None:
    """อัปเดต MT5_SERVER_TZ จาก tick.time จริงเทียบกับเวลา UTC ปัจจุบัน แทนเลข hardcode
    ที่ผิดไปครึ่งปีตอน broker สลับ DST — เรียกจาก mt5_ts_to_bkk() ทุกครั้งที่มี tick สด
    (throttle ด้วย _MT5_SERVER_TZ_REFRESH_SEC กันอัปเดตถี่เกินจำเป็น)

    ใส่ debounce ไว้ — ต้องเห็นค่า offset ใหม่ "ติดกัน" อย่างน้อย
    _MT5_SERVER_TZ_CONFIRM_COUNT ครั้ง (รวมแล้วหลายนาที) ก่อนจะ commit เป็นค่าจริง
    กัน tick กระตุก/sample ครั้งเดียวเพี้ยน (เช่น symbol เงียบ tick ไม่อัปเดตชั่วขณะ)
    ทำให้ MT5_SERVER_TZ สวิงผิดไป 1h กลางอากาศ แล้ว bar time label ที่ format ใหม่ทุก
    ครั้ง (ไม่ cache) ผิดตามไปด้วยทันที ทั้งที่ DST จริงๆเปลี่ยนปีละ 2 ครั้งเท่านั้น
    ไม่ควรสวิงถี่ขนาดนี้"""
    global MT5_SERVER_TZ, _mt5_server_tz_checked_at
    global _mt5_server_tz_pending, _mt5_server_tz_pending_count
    if (now_ts - _mt5_server_tz_checked_at) < _MT5_SERVER_TZ_REFRESH_SEC:
        return
    _mt5_server_tz_checked_at = now_ts
    offset = round((tick_ts - now_ts) / 3600.0)
    if not (-12 <= offset <= 14):
        return
    if offset == MT5_SERVER_TZ:
        _mt5_server_tz_pending = None
        _mt5_server_tz_pending_count = 0
        return
    if offset == _mt5_server_tz_pending:
        _mt5_server_tz_pending_count += 1
    else:
        _mt5_server_tz_pending = offset
        _mt5_server_tz_pending_count = 1
    if _mt5_server_tz_pending_count >= _MT5_SERVER_TZ_CONFIRM_COUNT:
        MT5_SERVER_TZ = offset
        _mt5_server_tz_pending = None
        _mt5_server_tz_pending_count = 0
        date_key = datetime.fromtimestamp(now_ts, tz=timezone.utc).strftime("%Y-%m-%d")
        if _MT5_SERVER_TZ_HISTORY.get(date_key) != offset:
            _MT5_SERVER_TZ_HISTORY[date_key] = offset
            _save_mt5_server_tz_history()

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
            dt_bkk = mt5_ts_to_bkk(best_ts)  # side effect: refresh MT5_SERVER_TZ
            if dt_bkk is not None:
                # เช็คความสดของ tick ก่อนเชื่อ — tick.time เข้ารหัสเป็น broker-local
                # clock (เทียบเท่า OS UTC now + MT5_SERVER_TZ ชม. ถ้าสด) ถ้า tick ค้าง
                # (เช่น ตอน reconnect ได้ tick เก่าจากก่อนหน้า) ห้ามเชื่อ ไม่งั้น "now"
                # จะผิดไปตามความ stale นั้น (เคสจริง: ผิดไปเกือบ 1 ชม.ตอน restart)
                actual = datetime.fromtimestamp(int(best_ts), tz=timezone.utc)
                expected = datetime.now(timezone.utc) + timedelta(hours=MT5_SERVER_TZ)
                if abs((actual - expected).total_seconds()) <= 30:
                    return dt_bkk
    except Exception:
        pass
    return datetime.now(timezone.utc) + timedelta(hours=TZ_OFFSET)


def mt5_ts_to_bkk(ts: int | float | None) -> datetime | None:
    """แปลง MT5 server timestamp (bar/sweep/deal/tick time) เป็นเวลา Bangkok จริง
    (UTC+7, ตรงกับหน้าจอ MT5 terminal) ตามส่วนต่าง server -> BKK"""
    try:
        if ts is None:
            return None
        ts_int = int(ts)
        _refresh_mt5_server_tz(ts_int, datetime.now(timezone.utc).timestamp())
        return datetime.fromtimestamp(ts_int, tz=timezone.utc) + timedelta(hours=TZ_OFFSET - MT5_SERVER_TZ)
    except Exception:
        return None


def fmt_mt5_bkk_ts(ts: int | float | None, fmt: str = "%H:%M:%S %d/%m/%Y") -> str:
    """format MT5 server timestamp เป็นเวลา Bangkok"""
    dt = mt5_ts_to_bkk(ts)
    return dt.strftime(fmt) if dt is not None else "-"


def _mt5_server_tz_for_ts(ts: int) -> int:
    """หา MT5_SERVER_TZ ของ 'วันนั้น' จาก history แทนค่าปัจจุบัน
    fallback เป็นค่าปัจจุบันถ้าวันนั้นยังไม่มีบันทึก (เช่น ก่อนเริ่มเก็บ history)"""
    try:
        date_key = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return MT5_SERVER_TZ
    return int(_MT5_SERVER_TZ_HISTORY.get(date_key, MT5_SERVER_TZ))


def mt5_server_tz_for_ts(ts: int) -> int:
    """public wrapper ของ _mt5_server_tz_for_ts — ใช้นอกไฟล์นี้เวลาต้องเทียบ
    raw bar time (r['time']) ของ "วันเก่า" กับ timestamp ที่แปลงเป็น true UTC แล้ว"""
    return _mt5_server_tz_for_ts(ts)


def mt5_ts_to_bkk_hist(ts: int | float | None) -> datetime | None:
    """แปลง MT5 server timestamp (เก่า/ของวันก่อน) เป็นเวลา Bangkok โดยใช้
    MT5_SERVER_TZ ของ 'วันที่ ts เกิดขึ้นจริง' จาก history แทนค่าปัจจุบัน
    ใช้กับ deal/order/candle ของ ticket เก่า (เช่น Deal History footer,
    ticket lookup candle block) กัน MT5_SERVER_TZ เปลี่ยนข้ามวันแล้วแสดงผลผิด"""
    try:
        if ts is None:
            return None
        ts_int = int(ts)
        offset = _mt5_server_tz_for_ts(ts_int)
        return datetime.fromtimestamp(ts_int, tz=timezone.utc) + timedelta(hours=TZ_OFFSET - offset)
    except Exception:
        return None


def fmt_mt5_bkk_ts_hist(ts: int | float | None, fmt: str = "%H:%M:%S %d/%m/%Y") -> str:
    """format MT5 server timestamp (เก่า) เป็นเวลา Bangkok ด้วย mt5_ts_to_bkk_hist"""
    dt = mt5_ts_to_bkk_hist(ts)
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


def _symbol_root(symbol: str) -> str:
    text = str(symbol or "").strip().upper()
    m = re.match(r"([A-Z]+)", text)
    return m.group(1) if m else text


def _symbol_config_key(symbol: str) -> str:
    root = _symbol_root(symbol)
    if root.startswith("BTCUSD"):
        return "BTCUSD.iux"
    return "XAUUSD.iux"


def _symbol_candidate_names(symbol: str) -> list[str]:
    root = _symbol_root(symbol)
    configured = [
        s.strip()
        for s in str(SYMBOL_CANDIDATES or "").split(",")
        if s.strip() and _symbol_root(s.strip()) == root
    ]
    common = [
        symbol,
        root,
        f"{root}.iux",
        f"{root}-VIPc",
        f"{root}c",
        f"{root}m",
    ]
    for name in SYMBOL_CONFIG.keys():
        if _symbol_root(name) == root:
            common.append(name)
    seen, out = set(), []
    for item in configured + common:
        key = str(item).strip()
        if key and key.upper() not in seen:
            seen.add(key.upper())
            out.append(key)
    return out


def resolve_mt5_symbol(mt5_module=None, symbol: str | None = None, set_runtime: bool = True) -> str:
    """Resolve generic SYMBOL like XAUUSD to the broker-specific symbol name."""
    mt5_api = mt5_module or mt5
    desired = str(symbol if symbol is not None else SYMBOL or "").strip()
    if not desired:
        return desired

    for candidate in _symbol_candidate_names(desired):
        try:
            info = mt5_api.symbol_info(candidate)
        except Exception:
            info = None
        if info is not None:
            try:
                mt5_api.symbol_select(candidate, True)
            except Exception:
                pass
            if set_runtime and candidate != SYMBOL:
                set_runtime_symbol(candidate)
            return candidate

    root = _symbol_root(desired)
    try:
        symbols = mt5_api.symbols_get(f"{root}*") or []
    except Exception:
        symbols = []
    matches = []
    for item in symbols:
        name = str(getattr(item, "name", "") or "")
        if name.upper().startswith(root):
            matches.append(name)
    for candidate in sorted(matches, key=lambda s: (0 if s.upper() == root else 1, len(s), s)):
        try:
            mt5_api.symbol_select(candidate, True)
        except Exception:
            pass
        if set_runtime and candidate != SYMBOL:
            set_runtime_symbol(candidate)
        return candidate
    return desired


def symbol_family_config() -> dict:
    return SYMBOL_CONFIG.get(SYMBOL, SYMBOL_CONFIG.get(_symbol_config_key(SYMBOL), SYMBOL_CONFIG["XAUUSD.iux"]))


def mt5_initialize(mt5_module=None, login: bool = True, resolve: bool = True) -> bool:
    """Initialize direct MetaTrader5 scripts with the active profile path/login."""
    mt5_api = mt5_module or mt5
    init_kwargs = {"timeout": MT5_TIMEOUT_MS}
    if MT5_PATH:
        init_kwargs["path"] = MT5_PATH
        init_kwargs["portable"] = MT5_PORTABLE
    ok = bool(mt5_api.initialize(**init_kwargs))
    if not ok:
        return False
    if login and MT5_LOGIN:
        try:
            info = mt5_api.account_info()
        except Exception:
            info = None
        if info is None or int(getattr(info, "login", 0) or 0) != int(MT5_LOGIN):
            ok = bool(mt5_api.login(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER))
            if not ok:
                return False
    if resolve:
        resolve_mt5_symbol(mt5_api)
    return True


def profile_symbol(symbol: str | None = None, mt5_module=None, set_runtime: bool = False) -> str:
    """Resolve a generic or configured symbol for scripts/backtests."""
    return resolve_mt5_symbol(mt5_module or mt5, symbol or SYMBOL, set_runtime=set_runtime)

# ============================================================
#  SETTINGS
# ============================================================
TELEGRAM_TOKEN = "8731980788:AAHJ1_L3F44ZZbxR3yrPQhtZQzxgQE0d5s0"
MY_USER_ID     = 8666020453
SYMBOL         = "XAUUSD"   # runtime resolves this to broker-specific symbol suffix
SYMBOL_CANDIDATES = ""
symbol_switch_in_progress = False  # True ระหว่าง check_symbol_switch กำลังสลับ symbol (กัน order race)

# ── config ต่อ symbol ─────────────────────────────────────────
SYMBOL_CONFIG = {
    "XAUUSD.iux": {"sl_buffer": 2.0,  "volume": 0.01},
    "BTCUSD.iux": {"sl_buffer": 50.0, "volume": 0.01},
}
MT5_LOGIN      = 2101114448
MT5_PASSWORD   = "cop04TERZ_18"
MT5_SERVER     = "IUXMarkets-Demo"
MT5_PATH       = ""
MT5_PORTABLE   = True
MT5_TIMEOUT_MS = 120000
MAGIC_NUMBER   = 234001

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", TELEGRAM_TOKEN)
MY_USER_ID     = int(os.getenv("MY_USER_ID", os.getenv("TELEGRAM_USER_ID", str(MY_USER_ID))) or MY_USER_ID)
SYMBOL         = os.getenv("SYMBOL", SYMBOL)
SYMBOL_CANDIDATES = os.getenv("SYMBOL_CANDIDATES", SYMBOL_CANDIDATES)
MT5_LOGIN      = int(os.getenv("MT5_LOGIN", str(MT5_LOGIN)) or MT5_LOGIN)
MT5_PASSWORD   = os.getenv("MT5_PASSWORD", MT5_PASSWORD)
MT5_SERVER     = os.getenv("MT5_SERVER", MT5_SERVER)
MT5_PATH       = os.getenv("MT5_PATH", MT5_PATH)
MT5_PORTABLE   = os.getenv("MT5_PORTABLE", str(MT5_PORTABLE)).strip().lower() in ("1", "true", "yes", "on")
MT5_TIMEOUT_MS = int(os.getenv("MT5_TIMEOUT_MS", str(MT5_TIMEOUT_MS)) or MT5_TIMEOUT_MS)
MAGIC_NUMBER   = int(os.getenv("MAGIC_NUMBER", str(MAGIC_NUMBER)) or MAGIC_NUMBER)

AUTO_VOLUME    = 0.01   # lot size สำหรับ auto trade (ฐานของ XAUUSD)


def points_scale() -> float:
    """
    Multiplier สำหรับ point/lot ตาม SYMBOL ปัจจุบัน
    XAUUSD = 1.0 (default), BTCUSD = 4.0
    ใช้ background ทุกที่ที่คำนวณ point → price (ไม่กระทบค่าใน Telegram UI)
    """
    if str(SYMBOL).upper().startswith("BTCUSD"):
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

# ── Standalone Strategy / Filter Skip Configs ──────────────
# การตั้งค่าให้ Strategy ที่เจาะจงข้ามระบบป้องกันส่วนกลาง
PENDING_LIMIT_GUARD_SKIP_SIDS = {20.5, 20.6, 20.7, 20.8, 20.9, 20.10, 20.11, 20.12, 21}
NEWS_FILTER_SKIP_SIDS         = {20.5, 20.6, 20.7, 20.8, 20.9, 20.10, 20.11, 20.12, 21}
SL_GUARD_SKIP_SIDS            = {1, 10, 14, 20.5, 20.6, 20.7, 20.8, 20.9, 20.10, 20.11, 20.12, 21}
SL_GUARD_GROUP_SKIP_SIDS      = {1, 20.5, 20.6, 20.7, 20.8, 20.9, 20.10, 20.11, 20.12, 21}
OPPOSITE_ORDER_SKIP_SIDS      = {10, 12, 13, 15, 16, 17, 18, 19, 20.5, 20.6, 20.7, 20.8, 20.9, 20.10, 20.11, 20.12, 21}
PDFIBOPLUS_SKIP_SIDS          = {1, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20.5, 20.6, 20.7, 20.8, 20.9, 20.10, 20.11, 20.12, 21}
STRONG_TREND_BLOCK_SIDS       = [9, 10, 11, 13, 14, 15, 16, 17] # เฉพาะท่าในลิสต์นี้จะถูกบล็อกเวลาเทรนแรง
# ────────────────────────────────────────────────────────

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
    return symbol_family_config()["sl_buffer"]

# ── ท่าที่ 1: Zone filter mode ───────────────────────────────
# "zone"   = ต้องอยู่ใกล้ Swing Low/High (เดิม)
# "normal" = ไม่สนใจ zone (เข้าได้ทุก pattern ที่ผ่านเงื่อนไข)
# "swing"  = ต้องมี swing เกิดขึ้นฝั่งเดียวกันภายใน 4 แท่งหลังเกิด setup
S1_ZONE_MODE = "swing"
S1_P6_ENABLED = False  # S1 Pattern F / P6 disabled

# ── ท่าที่ 1: Rejection Entry ─────────────────────────────────
# เช็คแท่ง entry (แท่งที่ order fill) หลังแท่งนั้นปิด — ถ้าไม่เข้าเงื่อนไข
# ปิด position ทันที + ปิด S11 ที่ผูกกับ TF เดียวกันด้วย
# BUY:  body% <= 40% และไส้ล่าง > ไส้บน และต้องมีไส้บน
# SELL: body% <= 40% และไส้บน > ไส้ล่าง และต้องมีไส้ล่าง
S1_REJECTION_ENTRY_ENABLED = True

# ── ท่าไม้ตายอออิน 4 วิ (S20) VIP Features ────────────────
S20_USE_PSYCHOLOGICAL_NUMBERS = True
S20_PSYCHO_DIGITS = [7, 8, 9]  # เลขจิตวิทยาที่ใช้หลีกเลี่ยง 0 และ 5
S20_DYNAMIC_FIBO = True        # หดเป้า RUN เหลือ KRH2 อัตโนมัติถ้าแท่งฐานใหญ่เกินไป

# ── News Filter API ───────────────────────────────
NEWS_FILTER_ENABLED = True
NEWS_EMBARGO_BEFORE_MINS = 15
NEWS_EMBARGO_AFTER_MINS = 15

news_pause_active = False

# ── ML Scoring ───────────────────────────────
ML_SCORING_ENABLED = True
ML_PROB_THRESHOLD = 0.45

# ── Observable Mode (Ghost Mode) ────────────────
OBSERVABLE_MODE = True
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
        try:
            from bot_log import log_error as _lerr
            _lerr("TG_SEND_ERROR", f"{type(e).__name__}: {e}")
        except Exception:
            pass


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
                        _preview = (text or "").replace("\n", " | ")[:1200]
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
                            _le("TG_SENT", "[retry-plain] " + (retry_text or "").replace("\n", " | ")[:1180])
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

                # ── auto-fix: Timed out → retry a few times before dropping ──
                elif "timed out" in err_str.lower():
                    for _attempt, _delay in enumerate((3, 6, 10), start=1):
                        await asyncio.sleep(_delay)
                        try:
                            await self._send(chat_id=chat_id, text=final_text, parse_mode=parse_mode, **kwargs)
                            _retried = True
                            _log_sent_retry(final_text)
                            break
                        except Exception as _re:
                            _retry_err = _re
                            try:
                                await self._send(chat_id=chat_id, text=final_text, parse_mode=None, **kwargs)
                                _retried = True
                                _log_sent_retry(final_text)
                                break
                            except Exception as _plain_re:
                                _retry_err = _plain_re

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
    15: True,  # ท่าที่ 15: Volume Profile POC + Absorption (Win Rate 85-90%)
    16: True,  # ท่าที่ 16: AMD x iFVG
    17: True,  # ท่าที่ 17: Sweep Sniper (Triple-Confluence — TP สั้น เน้น win rate สูง)
    18: True,  # ท่าที่ 18: TJR ICT
    19: True,  # ท่าที่ 19: ICT Advanced (Silver Bullet/Breaker/BPR)
    20: False,  # ท่าที่ 20: All in 4s (Reversal & Retracement)
    20.7: False, # ท่าที่ 20.7: ท่าไม้ตายอออิน4วิ 1 (Defect & Wick Fill Divergence)
    20.5: False, # S20.5: Fibo Standalone
    20.6: False,  # S20.6: FVG Standalone
    20.8: False, # ท่าที่ 20.8: อออิน4วิ 2 (Rejection)
    20.9: False, # ท่าที่ 20.9: Candle Action
    20.10: False, # ท่าที่ 20.10: Allin4s_2 (Reversal Trap)
    20.11: False, # ท่าที่ 20.11: Candle Strength
    20.12: False, # ท่าที่ 20.12: FutureKey
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
    16: "ท่าที่ 16: AMD iFVG",
    17: "ท่าที่ 17: Sweep Sniper",
    18: "ท่าที่ 18: TJR ICT",
    19: "ท่าที่ 19: ICT Silver Bullet",
    20: "ท่าที่ 20: All in 4s",
    20.5: "S20.5: Fibo Standalone",
    20.6: "S20.6: FVG Standalone",
    20.7: "S20.7: อออิน4วิ 1",
    20.8: "S20.8: อออิน4วิ 2",
    20.9: "S20.9: Candle Action",
    20.10: "S20.10: Wick Purge",
    20.11: "S20.11: Candle Strength",
    20.12: "S20.12: FutureKey",
}

# ── Strategy 20: All in 4s (Reversal & Retracement) ─────────
# "เนื้อคลุมเนื้อ" reversal + 50% retracement entry (หรือปลายไส้)
# Cancel limit ถ้ารอเกิน S20_CANCEL_BARS, TP อัตโนมัติที่ Fibo 161.8%
S20_ENABLED           = False
S20_7_ENABLED         = False
S20_8_ENABLED         = False
S20_5_COMPOUNDING_ENABLED = False
S20_5_RISK_PCT        = 2.0
S20_5_MAX_LOT         = 50.0
S20_5_TF_ENABLED      = {"M1": True, "M5": True, "M15": True, "M30": True, "H1": True, "H4": True}
S20_6_COMPOUNDING_ENABLED = False
S20_6_RISK_PCT        = 2.0
S20_6_MAX_LOT         = 50.0
S20_8_COMPOUNDING_ENABLED = False
S20_8_RISK_PCT        = 2.0
S20_8_MAX_LOT         = 50.0
S20_9_ENABLED         = False
S20_10_ENABLED        = False
S20_10_COMPOUNDING_ENABLED = False
S20_10_RISK_PCT       = 2.0
S20_10_MAX_LOT        = 50.0
S20_10_USE_PSYCHOLOGICAL_NUMBERS = True

S20_11_ENABLED        = False
S20_11_TF_ENABLED     = {"M1": True, "M5": True, "M15": True, "M30": True, "H1": True, "H4": True, "H12": True, "D1": True}
S20_11_COMPOUNDING_ENABLED = False
S20_11_RISK_PCT       = 2.0
S20_11_MAX_LOT        = 50.0

S20_12_ENABLED        = False
S20_12_TF_ENABLED     = {"M1": True, "M5": True, "M15": True, "M30": True, "H1": True, "H4": True, "H12": True, "D1": True}
S20_12_COMPOUNDING_ENABLED = True
S20_12_RISK_PCT       = 2.0
S20_12_MAX_LOT        = 50.0
S20_12_SESSION_FILTER = False


S20_8_POINTS_MULTIPLIER = 0.01
S20_ALLOWED_TFS       = ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1"]
S20_CANCEL_BARS       = 5
S20_FIBO_TP_LEVEL     = 1.618
S20_SL_BUFFER         = 1.0  # SL = ไส้ extreme ∓ ATR × นี้
# ── S20 WR Improvement Filters ──────────────────────────────
S20_MIN_BODY_ATR_PCT  = 0.3  # engulf body ต้อง ≥ 30% ของ ATR (กรอง noise)
S20_SESSION_FILTER    = False # เทรดเฉพาะ Killzones (London/NY)
S20_SESSIONS          = [("14:00", "18:00"), ("19:00", "23:00")]  # BKK
S20_TREND_FILTER      = False # block signal ที่สวน strong trend (HHLL)

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
# S14_SWEEP_SWING  : BSS/SSS  — Engulf ใน TF + HTF swept กลับมาเหนือ ref (ใช้ HHLL สำหรับ ref)
# S14_ENGULF_SWING : BSSM30 ฯลฯ — Engulf ใน TF + HTF ทะลุ ref + sec_HTF กำลัง sweep (ใช้ HHLL + sec_HTF)
# S14_SWEEP_RETURN : BRS/SRS  — ไส้ยาวกลับมา ไม่มี HTF check
S14_SWEEP_SWING       = True
S14_ENGULF_SWING      = True
S14_SWEEP_RETURN      = False   # BRS/SRS — ไส้เกิน LL/HH แต่ปิดกลับมา
S14_ENGULF_BREAKEVEN  = True   # ถ้า sec_HTF ปิดต่ำกว่า ref_low หลัง entry → ตั้ง TP = entry price
S14_BLOCK_SIDEWAY     = False   # block S14 ใน SIDEWAY trend (data 06-2026: 0% WR, -$58 จาก 4 orders)
S14_FLIP_ENABLED      = True   # Flip: ปิดฝั่งตรงข้ามทันทีเมื่อ signal ใหม่มา (per-TF)
S14_RSI_MIN_DIFF      = 1.0   # RSI divergence ต้องห่างกัน > นี้ (BUY: cur-ref > 1, SELL: ref-cur > 1)
S14_RSI_DIV_ENABLED   = False   # เปิด/ปิดการตรวจจับ RSI Divergence สำหรับ S14 (default False)

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
# ── S15 improvements (02/06: BUY สวนเทรนด์ขาดทุน -177, ยิงซ้ำจุดเดิม) ──
S15_TREND_FILTER        = True  # BUY เฉพาะ close≥EMA, SELL เฉพาะ close≤EMA (กัน mean-rev สวนเทรนด์)
S15_TREND_EMA           = 50    # period EMA สำหรับ trend filter
S15_TREND_NEUTRAL_ATR   = 0.1   # neutral band = ATR × นี้ (ในแบนด์นี้ทั้ง BUY/SELL ได้)
S15_LEVEL_COOLDOWN_BARS  = 15   # ห้ามยิง LIMIT ซ้ำที่ POC/VAL/VAH เดิมภายใน N แท่ง
S15_GLOBAL_COOLDOWN_SECS = 300  # หลัง S15 fire ใด TF → block ทุก TF อีก N วินาที (กัน multi-TF cluster)
S15_STRICT_MODE          = True # เข้าเฉพาะ VAL-BUY/VAH-SELL ที่มี 2-bar reversal (กรอง setup อ่อน + ข้าม POC)
S15_RSI_FILTER           = True # RSI momentum filter: BUY ต้อง RSI<S15_RSI_BUY_MAX, SELL ต้อง RSI>S15_RSI_SELL_MIN
S15_RSI_PERIOD          = 14    # RSI period
S15_RSI_BUY_MAX         = 60    # BUY เข้าเฉพาะ RSI ≤ นี้ (momentum ยังไม่ overbought)
S15_RSI_SELL_MIN        = 40    # SELL เข้าเฉพาะ RSI ≥ นี้ (momentum ยังไม่ oversold)

# ── Strategy 16: AMD x iFVG ──────────────────────────────────────────
S16_ASIAN_START_BKK      = "08:00"
S16_ASIAN_END_BKK        = "12:00"
S16_KILLZONES            = [("14:00", "17:00"), ("19:00", "22:00")]
S16_MIN_RR               = 1.5
S16_ENTRY_MODE           = "boundary"  # "boundary" (ขอบ FVG) หรือ "midline" (50% ของ FVG)
# ── S16 fixes 11/06/2026 (จากข้อมูล order จริง 08-10/06: -510.54 USD) ──
# 1. one-shot dedup ต่อ (tf, side, killzone) ใน s16_state["fired"] — แก้ 13 ไม้ fill พร้อมกัน
# 2. SL buffer ของตัวเอง — เดิมใช้ SL_BUFFER กลาง 2×ATR → แพ้เฉลี่ย -$30..-$49/ไม้
# sim A/B (24/05-11/06 M1+M5+M15): เดิม -145.51 → one-shot -173.11 → SLbuf1.0 -71.71
#   → SLbuf0.5 -15.38 (ดีสุด; 0.3 แย่ลง -57.00) — ยังติดลบทุก config ที่เทสมา
# ⚠️ sim 60 วัน (sim_s16_backtest.py, 22/06): M1 ยังขาดทุนหนัก WR 6.7% แพ้ติด 24 ไม้
#   ติดลบทุก TF (ยกเว้น H1 n=1 ข้อมูลน้อยเกินเชื่อ) — ทั้ง BUY/SELL แพ้เท่ากัน (ไม่ใช่ direction bias)
#   พี่ตัดสินใจคง active_strategies[16]=True ไว้ (22/06/2026) ทั้งที่ backtest ยังลบ — โปรดระวัง
S16_SL_ATR_BUFFER        = 0.5   # SL = sweep extreme ∓ ATR × นี้ (None = ใช้ SL_BUFFER กลาง)
S16_MAX_RISK_ATR_MULT    = 4.0   # skip setup ที่ risk > ATR × นี้ (0 = ปิด)
S16_KZ_ONE_SHOT          = True  # 1 order ต่อ (side, killzone) — runtime บังคับเสมอ; flag ใช้ใน sim A/B

# ── Strategy 17: Sweep Sniper (Triple-Confluence Mean Reversion) ─────
# ⚠️ win rate สูงมาจาก TP สั้น (RR ต่ำ) — 1 SL กิน TP หลายไม้ ต้องคุม lot
# default ปรับจาก backtest 30+60 วัน (sim_s17_backtest.py, 06/2026):
#   M1 60 วัน: n=248 WR 91.1% P/L +$78.90 ต่อ 0.01 lot, แพ้ติดกันสูงสุด 2
#   ทางเลือก TP 0.4 → WR 87.1% แต่กำไรมากกว่า (+$89.73)
S17_ALLOWED_TFS         = ["M1", "M5", "M15", "M30", "H1", "H4"]  # backtest 60d: M1 ดีสุด (+$60 WR93%), M5 ลบ, M30/H1 บวกแต่ n น้อย
S17_LOOKBACK            = 60    # bars กรอบอ้างอิง sweep + fib zone
S17_RSI_PERIOD          = 14
S17_RSI_BUY_MAX         = 32    # BUY เข้าเฉพาะ RSI แท่ง signal ≤ นี้
S17_RSI_SELL_MIN        = 68    # SELL เข้าเฉพาะ RSI แท่ง signal ≥ นี้
S17_WICK_MIN_PCT        = 0.30  # ไส้ฝั่ง sweep ขั้นต่ำ (% ของ range แท่ง)
S17_TP_ATR_MULT         = 0.3   # TP = entry ± ATR × นี้ (สั้น = win rate สูง)
S17_SL_ATR_BUFFER       = 1.0   # SL = ไส้ sweep ∓ ATR × นี้ (buffer ของ S17 เอง — ไม่ใช้ SL_BUFFER กลาง)
S17_MAX_RISK_ATR_MULT   = 4.0   # skip ถ้า SL ห่างเกิน ATR × นี้
S17_PD_FILTER           = True  # close แท่ง signal ต้องอยู่ Discount/Premium (fib 38.2/61.8)
S17_ENTRY_MODE          = "limit_618"  # "limit_618"=retrace 61.8% | "limit_50"=50% | "market"
S17_LIMIT_CANCEL_BARS   = 5     # limit ไม่ fill ภายใน N แท่ง → ยกเลิก (กลไก cancel_bars กลาง)
S17_TREND_FILTER        = False # EMA slope filter (backtest 06/2026: ตัด setup เกือบหมด — ปิดไว้)
S17_TREND_EMA           = 50
S17_TREND_SLOPE_BARS    = 10
S17_TIME_STOP_BARS      = 0     # ปิดไม้ที่แช่เกิน N แท่ง (0 = ปิดใช้งาน; ใช้ใน sim — backtest: ไม่ช่วย)
S17_SESSION_FILTER      = True  # เทรดเฉพาะ Killzones
S17_SESSIONS            = [("14:00", "18:00"), ("19:00", "23:00")]  # BKK London/NY
S17_LEVEL_COOLDOWN_BARS = 20    # กันยิงซ้ำ level เดิมภายใน N แท่ง

# ── Strategy 18: TJR / ICT Full-Confluence (Standalone) ──────────────
# ครบทุกชั้นจึงเข้า: HTF bias → sweep → MSS/CHOCH → FVG/OB ใน OTE → killzone
# ⚠️ ค่าด้านล่างเป็น default ตั้งต้นก่อน backtest — ปรับจูนหลังรัน sim_s18_backtest.py
S18_ALLOWED_TFS         = ["M1", "M5"]  # entry TF (bias มาจาก HTF map)
S18_LOOKBACK            = 60     # bars กรอบหา sweep + structure + fib leg
S18_HTF_MAP             = {"M1": "M15", "M5": "H1", "M15": "H1",
                           "M30": "H4", "H1": "H4", "H4": "D1"}
S18_REQUIRE_HTF_BIAS    = True   # บังคับเทรดตามทิศ HTF (False = แค่ห้ามสวนทาง)
S18_RSI_FILTER          = True
S18_RSI_PERIOD          = 14
S18_RSI_BUY_MAX         = 45     # OTE BUY: retrace ไม่ต้อง extreme เท่า S17
S18_RSI_SELL_MIN        = 55
S18_OTE_LO              = 0.62   # OTE band 62–79% ของ leg (sweep→MSS)
S18_OTE_HI              = 0.79
S18_ZONE_PREFER         = "fvg"  # "fvg" ก่อน, fallback "ob" (หรือ "ob")
S18_ENTRY_MODE          = "zone_edge"  # "zone_edge" (ขอบใกล้ราคา) | "zone_mid"
S18_SL_ATR_BUFFER       = 1.0    # SL = ไส้ sweep ∓ ATR × นี้
S18_RR_TARGET           = 2.0    # เป้า RR เมื่อ fallback หา TP
S18_MIN_RR              = 1.5    # RR ขั้นต่ำที่ยอมเข้า
S18_MAX_RISK_ATR_MULT   = 6.0    # skip ถ้า risk > ATR × นี้
S18_LIMIT_CANCEL_BARS   = 8      # limit ไม่ fill ภายใน N แท่ง → ยกเลิก
S18_SESSION_FILTER      = True   # เทรดเฉพาะ Killzones London/NY
S18_SESSIONS            = [("14:00", "18:00"), ("19:00", "23:00")]  # BKK
S18_LEVEL_COOLDOWN_BARS = 20     # กันยิงซ้ำ level เดิมภายใน N แท่ง

# ── Strategy 19: ICT Advanced (Silver Bullet + Breaker + BPR) (Standalone) ──
# ต่อยอด S18: Silver Bullet window แคบ + Breaker Block + BPR + Power of 3 + NDOG
# ⚠️ ค่าด้านล่างเป็น default ตั้งต้นก่อน backtest — ปรับจูนหลังรัน sim_s19_backtest.py
S19_ALLOWED_TFS          = ["M1", "M5"]  # entry TF (bias มาจาก HTF map)
S19_LOOKBACK             = 60     # bars กรอบหา sweep + structure + zone
S19_HTF_MAP              = {"M1": "M15", "M5": "H1", "M15": "H1",
                            "M30": "H4", "H1": "H4", "H4": "D1"}
S19_REQUIRE_HTF_BIAS     = True   # บังคับเทรดตามทิศ HTF
S19_SESSION_FILTER       = True   # เทรดเฉพาะ Silver Bullet windows
S19_SILVER_BULLET_SESSIONS = [("13:00", "15:00"), ("21:00", "23:00")]  # BKK (London/NY AM)
S19_P3_SESSION_SWEEP     = True   # Power of 3: sweep ต้องอยู่ใน SB session เดียวกัน
S19_WICK_MIN_PCT         = 0.30   # rejection wick ขั้นต่ำ (สำรองไว้สำหรับจูน)
S19_USE_BREAKER          = True   # เปิด Breaker Block detector
S19_USE_BPR              = True   # เปิด Balanced Price Range detector
S19_USE_FVG_FALLBACK     = True   # fallback FVG ถ้าไม่มี Breaker/BPR
S19_USE_NDOG             = True   # ใช้ New Day Opening Gap เป็น TP target (ถ้าในทิศ)
S19_ZONE_PREFER          = "breaker"  # ลำดับเลือกโซน: breaker → bpr → fvg
S19_BPR_MIN_SIZE         = 0.01   # BPR overlap แคบกว่านี้ → ข้าม
S19_RSI_FILTER           = False  # SB ใช้เวลา/โครงสร้างเป็นหลัก (ไม่บังคับ RSI)
S19_RSI_PERIOD           = 14
S19_RSI_BUY_MAX          = 50     # ใช้เมื่อ S19_RSI_FILTER = True
S19_RSI_SELL_MIN         = 50
S19_OTE_LO               = 0.62   # OTE band 62–79% ของ leg (sweep→MSS)
S19_OTE_HI               = 0.79
S19_ENTRY_MODE           = "zone_edge"  # "zone_edge" (ขอบใกล้ราคา) | "zone_mid"
S19_SL_ATR_BUFFER        = 1.0    # SL = ไส้ sweep ∓ ATR × นี้
S19_RR_TARGET            = 2.0    # เป้า RR เมื่อ fallback หา TP
S19_MIN_RR               = 1.5    # RR ขั้นต่ำที่ยอมเข้า
S19_MAX_RISK_ATR_MULT    = 6.0    # skip ถ้า risk > ATR × นี้
S19_LIMIT_CANCEL_BARS    = 8      # limit ไม่ fill ภายใน N แท่ง → ยกเลิก
S19_LEVEL_COOLDOWN_BARS  = 20     # กันยิงซ้ำ level เดิมภายใน N แท่ง

# ── Strategy 20: All in 4s (Hardcore Mode + VIP Rules) ───────────────────
S20_ENABLED             = False
S20_ALLOWED_TFS         = ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1"]

# ── Stage 1: Base Triggers ──────────────────────────────────
S20_TRIGGER_DEFECT      = True  # ท่าดึงกลับมารอยแหว่ง, การดูดของ Defect
S20_TRIGGER_2L2H        = True  # โครงสร้างเบรคหลอก 2L/2H
S20_TRIGGER_SOLID_CLEAR = True  # การเด้งกลับจากแท่งตัน และแท่งเคลียร์
S20_TRIGGER_FVG_OB      = True  # การทดสอบ FVG และย่อ 50% ของแท่งแม่ (OB)
S20_TRIGGER_FIBO_ENTRY  = True  # ท่าย่อย S20.5: Fibo Entry
S20_5_ENABLED           = False # ท่าย่อย S20.5: Fibo Standalone (default ปิด — เปิด/ปิดผ่าน Telegram)
S20_6_FVG_ENABLED       = False # ท่าย่อย S20.6: FVG Standalone (default ปิด — เปิด/ปิดผ่าน Telegram)
S20_6_TF_ENABLED        = {"M1": True, "M5": True, "M15": True, "M30": True, "H1": True, "H4": True, "H12": True, "D1": True}
S20_6_SESSION_FILTER    = False
S20_6_SESSIONS          = [("14:00", "18:00"), ("19:00", "23:00")]
S20_6_TREND_FILTER      = False
S20_6_ENTRY_BUFFER      = 0

# ── Stage 2: Modifiers & Filters (ตัวช่วยความแม่นยำ) ────────────────
S20_MODIFIER_MAGIC_NUM  = True  # กรองด้วยเลขจิตวิทยา (เช่น 7)
S20_MODIFIER_SIGNIFICANT= True  # กรองด้วยแนวรับต้าน H4/D1 (ซ้อนทับ)
S20_MODIFIER_FIBO_CONF  = True  # กรองด้วย Fibo (138-161 Reverse / Base 0.0)
S20_MODIFIER_NO_BODY_BRK= True  # ยกเลิกถ้าราคาปิดทะลุแนวรับ/แนวต้าน

# ── Stage 3: Dynamic Exits ──────────────────────────────────
S20_CANCEL_ON_2L        = True  # ยกเลิกเมื่อเกิด 2L/2H สวนทางระหว่างรอ

S20_MIN_BODY_ATR_PCT    = 0.30
S20_SL_BUFFER           = 1.0
S20_SESSION_FILTER      = False
S20_SESSIONS            = [("14:00", "18:00"), ("19:00", "23:00")]
S20_ENTRY_BUFFER        = 390  # ระยะเผื่อเข้าดักไส้
S20_SL_2L2H             = 100  # SL สำหรับท่า 2L/2H ขนาดเล็ก

# Custom Fibo Constants for S20
S20_FIBO_KRH1       = 1.617
S20_FIBO_KRH2       = 3.097
S20_FIBO_KRH3       = 5.165
S20_FIBO_RUN        = 7.044
S20_DEFECT_FIBO_RUN = 7.467 # เป้าหมายพิเศษสำหรับท่าที่เล่นกับ Defect

# ── ท่าที่ 2 FVG Mode ────────────────────────────────────────
# FVG_NORMAL  = True  → ตั้ง order ทุก TF อิสระ (TF เดียวก็ order)
# FVG_PARALLEL = True → กรอง FVG ซ้ำจาก TF คู่ขนาน (ต้อง ≥2 TF ซ้อนทับ)
# เปิดทั้งคู่ได้: parallel จะรวม gap ถ้าเจอ ≥2 TF, ปกติจะ order TF เดี่ยวที่ parallel ไม่ได้จับ
FVG_NORMAL = True
FVG_PARALLEL = True
S2_NORMAL_CONFIRM_LOOKBACK_BARS = 8  # S2 แบบปกติ: ย้อนดู S1/S3 ฝั่งเดียวกันกี่แท่งก่อนยอมใช้ order
S3_CONFIRM_LOOKBACK_BARS = 8         # S3: ย้อนดู S1/S2/S3 ฝั่งเดียวกันกี่แท่งก่อนยอมใช้ order

# ── Adjacent-bar order guard (กันท่าเดียวกันยิงซ้อนแท่งติดกัน) ──
# True (default) = block เหมือนเดิม | False = ปิด guard นี้ ยอมให้ตั้ง order แท่งติดกันได้
S2_ADJACENT_BLOCK_ENABLED = False
S3_ADJACENT_BLOCK_ENABLED = False

# ── S2/S3 Chain Link (ใช้ได้ก็ต่อเมื่อ S2/S3 Adjacent Block ปิดทั้งคู่) ──
# pending S2/S3 ฝั่งเดียวกันบน TF เดียวกันที่ค้างอยู่พร้อมกัน (ไม่ต้องติดแท่งกัน)
# จะถูกรวมกลุ่ม — ตัวที่ fill ก่อน sync SL ให้ทุกตัวที่ fill ทีหลัง, ตัวที่ fill
# ล่าสุด sync TP ย้อนกลับให้ทุกตัวที่ fill ไปแล้ว และ cancel pending ที่เหลือถ้า
# ราคาปิดทะลุ swing (HHLL) ก่อนหน้าไปแล้ว — ใช้กับ S2/S3 เท่านั้น
S2_S3_CHAIN_LINK_ENABLED = True

# ── S2/S3 Chain Swing-Cancel (ลูกของ Chain Link) ──────────────────
# ถ้าราคาปิดทะลุ swing (HHLL) ก่อนหน้าไปแล้ว แต่ pending order ที่อยู่ใน
# chain group ยังไม่ fill เลยสักตัว (ไม่ต้องรอให้มีตัวไหน fill ก่อน) ให้
# ยกเลิก pending ที่เหลือทั้งหมดในกลุ่มทันที — ตั้งแยกได้ทีละ TF รวม M1 ด้วย
# (M1 ตั้งได้เหมือนกัน แต่ default ปิดไว้ก่อน — TF อื่น default เปิด)
S2_S3_CHAIN_SWING_CANCEL_ENABLED = True
S2_S3_CHAIN_SWING_CANCEL_TF = {
    "M1":  False,
    "M5":  True,
    "M15": True,
    "M30": True,
    "H1":  True,
    "H4":  True,
    "H12": True,
    "D1":  True,
}

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
LIMIT_TREND_RECHECK_ROUNDS = 1    # จำนวนรอบ: 1=เช็คหลัง fill, 2=+รอ H/L, 3=+รอ H/L อีกรอบ
TREND_FILTER_SCAN_BLOCK = False   # False = ไม่ block ตอน scan ให้ Limit Recheck จัดการแทน

# ── Premium/Discount Zone Recheck ──────────────────────────────────
# เช็ค limit order ว่าอยู่ใน zone ที่ถูกต้องไหม (ตาม HHLL swing H/L)
# BUY ต้องอยู่ใต้ EQ (Discount), SELL ต้องอยู่เหนือ EQ (Premium)
# ตรวจ 3 รอบ: (1) เมื่อเจอ order (2) H หรือ L ใหม่ (3) ทั้ง H และ L ใหม่
# ยกเลิก order ถ้า < 2/3 รอบผ่าน
PDFIBOPLUS_ENABLED = True


# ── Shared TP ──────────────────────────────────────────────────────
# ถ้ามี Position เปิดอยู่แล้วทิศทาง+TF เดียวกัน → order ใหม่ใช้ TP เดียวกับ
# position นั้นแทนที่จะคำนวณ swing TP ของตัวเอง (กัน position ทิศเดียวกัน
# บน TF เดียวกันถือ TP คนละค่า) ไม่กระทบ SL — sid 12/13 ข้ามเสมอ
SHARED_TP_ENABLED = True

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

# ── Pending Trend Check on Approach ───────────────────────────────────────────
# เมื่อราคาเข้าใกล้ entry ≤ N จุด → เช็ค trend ก่อน fill
# FAIL → ยกเลิก pending ทันที (ก่อนเสีย spread + slippage)
# PASS → จำ swing H/L ไว้ รอ swing ใหม่ → round 2
# Skip: S9, S10, S14, S15 (เหมือน check_fill_trend_recheck)
PENDING_TREND_CHECK_ENABLED = True
PENDING_TREND_CHECK_POINTS  = 200  # จุดที่ถือว่า "กำลังเข้าใกล้"
PENDING_TREND_CHECK_ROUNDS  = 1    # จำนวนรอบ: 1=เช็คตอน approach อย่างเดียว, 2=+รอ swing ใหม่

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
SL_GUARD_LOSS_ENABLED   = True
SL_GUARD_LOSS_THRESHOLD = 2.5   # USD — ขาดทุนเกินนี้ถึงนับ
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
SL_GUARD_GROUP_ENABLED     = True   # default mode
SL_GUARD_GROUP_COUNT       = 2
SL_GUARD_GROUP_SWING_BARS  = 5      # จำนวนแท่งยืนยัน swing ก่อน unblock
SL_GUARD_GROUP_GROUPS: list = [
    ["H4",  "H12", "D1"],
    ["H1",  "H4",  "H12"],
    ["M30", "H1",  "H4"],
    ["M15", "M30", "H1"],
    ["M5",  "M15", "M30"],
    ["M1",  "M5",  "M15"],
    ["M1",  "M5"],
]

# ── Quant Engine ──────────────────────────────────────────────
QUANT_ENGINE_ENABLED = True             # เปิด/ปิด Quant Engine ตัวกรองส่วนกลาง
QUANT_ENGINE_ACTIVE_SIDS = []       # ระบุ SID ของท่าเทรดที่จะให้เปิดใช้ Quant (เว้นว่าง [] = ไม่เปิดใช้กับท่าไหนเลย, ใส่ [1, 2, 3...] เพื่อเปิดเฉพาะท่า)
QUANT_MIN_ML_SCORE = 50.0               # คะแนน ML ขั้นต่ำ (ถ้าต่ำกว่านี้ = REJECT)
QUANT_ATR_SL_MULTIPLIER = 1.5           # ตัวคูณ ATR เพื่อขยาย SL ช่วงเหวี่ยงแรง
QUANT_VOLATILITY_BLOCK_MULT = 3.0       # ถ้า ATR ล่าสุดมากกว่า ATR ค่าเฉลี่ย x เท่าตัวนี้ = REJECT (ข่าวออก/กราฟกระชาก)

# ── Limit Sweep ──────────────────────────────────────────────
# เมื่อ position ถูก fill แล้วแท่งจบสวนทาง (BUY→แดง close<prevLow / SELL→เขียว close>prevHigh)
# → ปิด position + ยกเลิก limit ทั้งหมดใน TF นั้น เหลือเฉพาะตัวใกล้ LL/HH
# → ถ้าไม่มี limit ใกล้ LL/HH → ตั้ง S8 ที่ LL/HH
LIMIT_SWEEP = False

# ── Daily Loss Limit / Kill Switch ───────────────────────────
# เมื่อ realized P/L สะสมของวัน (BKK) ติดลบเกิน threshold → ปิดทุก position,
# ยกเลิก pending ทั้งหมด, ปิด auto_active และแจ้ง Telegram (กัน strategy พังกินพอร์ต)
# - daily_stats: accumulator ของวัน (persist ลง bot_state.json) — roll อัตโนมัติเมื่อข้ามวัน
# - daily_loss_tripped: True หลัง trip แล้ว (กัน re-trigger ซ้ำในวันเดียวกัน)
DAILY_LOSS_LIMIT_ENABLED = False
DAILY_LOSS_LIMIT_USD     = 50.0   # ขาดทุนสะสมเกิน $N → kill switch
daily_stats = {"date": "", "realized": 0.0, "wins": 0, "losses": 0,
               "count": 0, "gross_win": 0.0, "gross_loss": 0.0}
daily_loss_tripped = False

# ── Daily Summary (Telegram) ─────────────────────────────────
# ส่งสรุปผลของวันอัตโนมัติทุกวันตามเวลา BKK ที่กำหนด
DAILY_SUMMARY_ENABLED = True
DAILY_SUMMARY_HOUR    = 23
DAILY_SUMMARY_MINUTE  = 0

# ── Dynamic Lot Sizing (% Risk per Trade) ────────────────────
# เมื่อเปิด: base lot ของแต่ละ order คำนวณจาก RISK_PERCENT × equity / ระยะ SL
# (ใช้ tick_value/tick_size ของ symbol ปัจจุบัน) แทน AUTO_VOLUME คงที่
# - clamp ไม่เกิน RISK_MAX_LOT และไม่ต่ำกว่า volume_min ของ broker
# - default OFF — ถ้า OFF พฤติกรรมเดิมไม่เปลี่ยน
RISK_PERCENT_ENABLED = False
RISK_PERCENT         = 0.5    # % ของ equity ที่ยอมเสียต่อ 1 ไม้ (ก่อน TSO scale)
RISK_MAX_LOT         = 0.20   # เพดาน lot ต่อไม้ (หลังคำนวณ risk, ก่อน TSO)

# ── Watchdog / Health Check ──────────────────────────────────
# job เบาทุก 1 นาที: เขียน heartbeat file + เช็ก MT5 connection + เช็ก scan ค้าง
# แจ้ง Telegram เมื่อ MT5 หลุด / scan ค้าง และเมื่อกลับมาปกติ (dedup กัน spam)
WATCHDOG_ENABLED   = True
WATCHDOG_STALE_SEC = 120          # ไม่มี scan สำเร็จเกิน N วิ (ขณะ auto ON) → แจ้งเตือน
last_scan_ts       = 0.0          # epoch ของ scan สำเร็จล่าสุด (set โดย main.run_scan)
_watchdog_mt5_ok   = True         # สถานะ MT5 ล่าสุดที่ watchdog เห็น (กันแจ้งซ้ำ)
_watchdog_scan_ok  = True         # สถานะ scan ล่าสุดที่ watchdog เห็น (กันแจ้งซ้ำ)

# ── STALL diagnostic watchdog ────────────────────────────────
# ถ้า event loop แข็ง (MT5 call ค้าง) นานเกินนี้ → faulthandler dump stack ทุก
# thread ไปไฟล์ logs/debug/stall_trace.log ก่อน supervisor จะ kill ที่ 180s
# (เผื่อ buffer 30s ให้ dump เสร็จก่อนโดน kill)
STALL_TRACE_TIMEOUT = 150.0
_stall_trace_file   = None        # file handle ที่ faulthandler ใช้เขียน (เปิดค้างไว้ตลอด process)


def write_heartbeat(mt5_ok: bool | None = None) -> None:
    """เขียน heartbeat file แบบ atomic — stamp `ts` ล่าสุดให้ external supervisor

    ใช้โดย heartbeat_job (ทุก 15s) และ run_watchdog (ทุก 60s) ใน main.py
    external supervisor (run_supervised.ps1) อ่าน `ts` เพื่อ detect event-loop hang:
    ถ้า ts ค้างเกิน threshold = loop แข็ง (เช่น MT5 blocking call ค้าง) → kill+restart
    *ไม่เรียก MT5* เพื่อไม่ให้ตัว heartbeat เองไปบล็อก/ค้างตาม loop
    mt5_ok=None → ใช้ค่า cached (_watchdog_mt5_ok); write temp+os.replace กัน partial read
    """
    import time
    if mt5_ok is None:
        mt5_ok = _watchdog_mt5_ok
    try:
        hb = (
            f"ts={int(time.time())}\n"
            f"bkk={now_bkk().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"mt5_ok={int(bool(mt5_ok))}\n"
            f"auto={int(bool(auto_active))}\n"
            f"last_scan={int(last_scan_ts)}\n"
            f"pid={os.getpid()}\n"
        )
        tmp = HEARTBEAT_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(hb)
        os.replace(tmp, HEARTBEAT_FILE)   # atomic บน Windows/POSIX
    except Exception:
        pass


def _today_bkk() -> str:
    """วันที่ปัจจุบันแบบ BKK (UTC+7) เป็น 'YYYY-MM-DD'"""
    return now_bkk().strftime("%Y-%m-%d")


def _roll_daily_stats():
    """reset accumulator ถ้าข้ามวัน (เทียบ date ปัจจุบัน BKK)"""
    global daily_loss_tripped
    today = _today_bkk()
    if daily_stats.get("date") != today:
        daily_stats.update({"date": today, "realized": 0.0, "wins": 0,
                            "losses": 0, "count": 0, "gross_win": 0.0,
                            "gross_loss": 0.0})
        daily_loss_tripped = False


def record_daily_close(profit: float) -> dict:
    """บันทึก realized P/L ของ position ที่เพิ่งปิด ลง daily accumulator
    คืน dict ของ daily_stats หลังอัปเดต (roll วันอัตโนมัติ)"""
    _roll_daily_stats()
    try:
        p = float(profit)
    except Exception:
        p = 0.0
    daily_stats["realized"] = round(daily_stats.get("realized", 0.0) + p, 2)
    daily_stats["count"] = daily_stats.get("count", 0) + 1
    if p >= 0:
        daily_stats["wins"] = daily_stats.get("wins", 0) + 1
        daily_stats["gross_win"] = round(daily_stats.get("gross_win", 0.0) + p, 2)
    else:
        daily_stats["losses"] = daily_stats.get("losses", 0) + 1
        daily_stats["gross_loss"] = round(daily_stats.get("gross_loss", 0.0) + p, 2)
    return daily_stats


def daily_loss_should_trip() -> bool:
    """True ถ้า realized ของวันติดลบเกิน threshold และยังไม่เคย trip วันนี้"""
    if not DAILY_LOSS_LIMIT_ENABLED or daily_loss_tripped:
        return False
    _roll_daily_stats()
    return daily_stats.get("realized", 0.0) <= -abs(float(DAILY_LOSS_LIMIT_USD))


def build_daily_summary_text() -> str:
    """สร้างข้อความสรุปผลของวัน (BKK) จาก daily_stats + account info"""
    _roll_daily_stats()
    s = daily_stats
    cnt = s.get("count", 0)
    wins = s.get("wins", 0)
    losses = s.get("losses", 0)
    realized = s.get("realized", 0.0)
    wr = (wins / cnt * 100.0) if cnt else 0.0
    pnl_e = "💰" if realized >= 0 else "💸"
    acc_line = ""
    try:
        info = mt5.account_info()
        if info:
            acc_line = f"💼 Balance: `{info.balance:.2f}` | Equity: `{info.equity:.2f}`\n"
    except Exception:
        pass
    halt_line = "🛑 *Kill switch ทำงานวันนี้*\n" if daily_loss_tripped else ""
    return (
        f"📊 *สรุปผลประจำวัน — {s.get('date','-')}*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"{acc_line}"
        f"{pnl_e} Realized P/L: `{realized:.2f}` USD\n"
        f"🔢 จำนวนไม้: `{cnt}` (✅{wins} / ❌{losses})\n"
        f"🎯 Win Rate: `{wr:.1f}%`\n"
        f"📈 รวมกำไร: `{s.get('gross_win',0.0):.2f}` | 📉 รวมขาดทุน: `{s.get('gross_loss',0.0):.2f}`\n"
        f"{halt_line}"
        f"⚙️ Auto: {'🟢ON' if auto_active else '🔴OFF'}"
    )


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

# ── Sweep Filter ─────────────────────────────────────────────────────
# เปิด/ปิดผ่าน Telegram ได้
# SWEEP_LOW  → Block SELL / Unblock BUY  (ราคา sweep LL แล้ว bounce)
# SWEEP_HIGH → Block BUY  / Unblock SELL (ราคา sweep HH แล้ว reject)
# Reset เมื่อ trend เปลี่ยน
SWEEP_FILTER_ENABLED = True    # เปิดใช้งาน (toggle via Telegram Settings → Trend Filter)

# Sweep expiry: sweep state จะหมดอายุหลังผ่านไป N นาที (กัน sweep เก่าค้าง override trend นานเกิน)
# 0 = ไม่หมดอายุ (persist จนกว่า trend/label เปลี่ยน — behavior เดิม)
# ตั้งค่าแยกตาม Timeframe (นาที) ให้สอดคล้องกับขนาดของแท่งเทียน
SWEEP_FILTER_EXPIRY_MIN = {
    "M1":  60,      # 1 ชั่วโมง (60 แท่ง)
    "M5":  180,     # 3 ชั่วโมง (36 แท่ง)
    "M15": 360,     # 6 ชั่วโมง (24 แท่ง)
    "M30": 720,     # 12 ชั่วโมง (24 แท่ง)
    "H1":  1440,    # 24 ชั่วโมง (24 แท่ง)
    "H4":  5760,    # 4 วัน (24 แท่ง)
    "H12": 17280,   # 12 วัน (24 แท่ง)
    "D1":  34560,   # 24 วัน (24 แท่ง)
}

# ตรวจจับ RSI Divergence ตามเงื่อนไขของ S14 (ถ้าเปิดเป็น True จะกรอง Sweep แม่นยำขึ้นแต่ความถี่ลดลงมาก)
SWEEP_FILTER_RSI_DIV_ENABLED = False


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


# ── Strategy 10: CRT TBS — runtime mode (constants ที่ helper ใช้ภายหลังอยู่ด้านล่าง) ──
# Bar mode: "2bar" (classic CRT — sweep+close ในแท่งเดียว) หรือ "3bar" (TBS — sweep+confirm แยก)
CRT_BAR_MODE = "2bar"
# Min sweep depth: sweep wick ต้องทะลุ parent อย่างน้อยกี่ % ของ parent range (กัน micro-sweep)
CRT_SWEEP_DEPTH_PCT = 0.10   # 10% of parent range
# Entry mode:
#   "htf" — เข้า market บน HTF ทันทีตอน detect (SL ใหญ่)
#   "mtf" (default) — HTF detect → arm → ลงไป LTF รอ color shift → entry (SL เล็ก, RR ดี)
CRT_ENTRY_MODE = "mtf"
# สำหรับโหมด MTF: True = รอให้แท่ง sweep ของ HTF ปิดสมบูรณ์ก่อนเพื่อคอนเฟิร์มการ sweep แล้วค่อยหาจุดเข้าบน LTF
#                False (default) = หาจุดเข้าบน LTF ทันทีที่ HTF เกิด pre-sweep (กำลัง sweep อยู่แต่ยังไม่ปิดแท่ง)
CRT_WAIT_HTF_CLOSE = True
# Min parent body percentage (สัดส่วนเนื้อเทียนขั้นต่ำของแท่งตั้งต้น อิงตามทฤษฎี CRT เพื่อกรองแท่ง Doji)
CRT_PARENT_MIN_BODY_PCT = 0.60  # 60% ของกรอบราคา (Range) ของแท่งตั้งต้น
# Sweep containment: แท่ง sweep ต้องไม่ทะลุฝั่งตรงข้ามของ parent ไปด้วย
#   BUY (sweep low):  sweep high ต้องไม่เกิน parent high
#   SELL (sweep high): sweep low ต้องไม่ต่ำกว่า parent low
CRT_SWEEP_CONTAIN_ENABLED = True
# Sweep close max %: แท่ง sweep (2bar) / แท่ง confirm (3bar) ต้องปิดไม่เกิน X% ของ parent range
#   BUY: close ต้องอยู่ครึ่งล่าง (<=mid) | SELL: close ต้องอยู่ครึ่งบน (>=mid)
CRT_SWEEP_CLOSE_MAX_PCT = 0.50  # 50% = จุดกึ่งกลางของ parent range
# Retry after SL: True = เก็บ arm ไว้หลัง SL hit (retry ได้บน HTF bar ถัดไป)
#   ถ้า HTF bar ปิดผ่าน parent low/high → invalidate arm ทันที
S10_RETRY_AFTER_SL = True

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

# ── Demo Portfolio (P13 "Champion" / P16 "Max-Yield Blend") ──────────────────
# ระบบทดสอบแยกอิสระจากบอทหลัก (S1-S20) — ใช้ demo_portfolio.py, state แยกที่
# demo_portfolio_state.json, magic number แยก (990013/990016), ไม่แตะ
# active_strategies/bot_state.json/trailing.py — คุมเปิด-ปิดผ่าน Telegram
# ⚠️ default = เปิดทั้งคู่ (ผู้ใช้ยืนยันแล้ว 2026-07-01) — หลัง bot restart/คอมดับแล้วรันใหม่
# จะเทรดจริงทันทีโดยไม่ต้องกด Telegram ยืนยันก่อน (ไม่มี safety-net auto-OFF อีกต่อไป)
# ถ้าต้องการปิดชั่วคราว ใช้ปุ่ม ⏸️ ในเมนู "🧪 Demo Portfolio" บน Telegram
DEMO_PORTFOLIO_ACTIVE = {"P13": True, "P16": True}     # default เปิดทั้งคู่
DEMO_PORTFOLIO_SCAN_INTERVAL = 5                       # นาที (เท่ากับ SCAN_INTERVAL เดิม)

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
    "S2_ADJACENT_BLOCK_ENABLED": S2_ADJACENT_BLOCK_ENABLED,
    "S3_ADJACENT_BLOCK_ENABLED": S3_ADJACENT_BLOCK_ENABLED,
    "S2_S3_CHAIN_LINK_ENABLED": S2_S3_CHAIN_LINK_ENABLED,
    "S2_S3_CHAIN_SWING_CANCEL_ENABLED": S2_S3_CHAIN_SWING_CANCEL_ENABLED,
    "S2_S3_CHAIN_SWING_CANCEL_TF": copy.deepcopy(S2_S3_CHAIN_SWING_CANCEL_TF),
    "ENTRY_CANDLE_MODE": ENTRY_CANDLE_MODE,
    "ENTRY_CLOSE_REVERSE_MARKET": ENTRY_CLOSE_REVERSE_MARKET,
    "ENTRY_CLOSE_REVERSE_LIMIT": ENTRY_CLOSE_REVERSE_LIMIT,
    "ENTRY_CANDLE_UPDATE_TP": ENTRY_CANDLE_UPDATE_TP,
    "OPPOSITE_ORDER_MODE": OPPOSITE_ORDER_MODE,
    "NEWS_FILTER_ENABLED": NEWS_FILTER_ENABLED,
    "ML_SCORING_ENABLED": True,
    "ML_PROB_THRESHOLD": ML_PROB_THRESHOLD,
    "OBSERVABLE_MODE": True,
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
    "SWEEP_FILTER_ENABLED": SWEEP_FILTER_ENABLED,
    "SWEEP_FILTER_RSI_DIV_ENABLED": SWEEP_FILTER_RSI_DIV_ENABLED,
    "TREND_FILTER_MODE": TREND_FILTER_MODE,
    "CRT_BAR_MODE": CRT_BAR_MODE,
    "CRT_SWEEP_DEPTH_PCT": CRT_SWEEP_DEPTH_PCT,
    "CRT_ENTRY_MODE": CRT_ENTRY_MODE,
    "CRT_WAIT_HTF_CLOSE": CRT_WAIT_HTF_CLOSE,
    "CRT_PARENT_MIN_BODY_PCT": CRT_PARENT_MIN_BODY_PCT,
    "CRT_SWEEP_CONTAIN_ENABLED": CRT_SWEEP_CONTAIN_ENABLED,
    "CRT_SWEEP_CLOSE_MAX_PCT": CRT_SWEEP_CLOSE_MAX_PCT,
    "RSI9_PLOT_BULLISH": RSI9_PLOT_BULLISH,
    "RSI9_PLOT_HIDDEN_BULLISH": RSI9_PLOT_HIDDEN_BULLISH,
    "RSI9_PLOT_BEARISH": RSI9_PLOT_BEARISH,
    "RSI9_PLOT_HIDDEN_BEARISH": RSI9_PLOT_HIDDEN_BEARISH,
    "NEAR_APPROACH_CANCEL_ENABLED": NEAR_APPROACH_CANCEL_ENABLED,
    "NEAR_APPROACH_CANCEL_POINTS": NEAR_APPROACH_CANCEL_POINTS,
    "NEAR_APPROACH_CANCEL_LOOKBACK": NEAR_APPROACH_CANCEL_LOOKBACK,
    "PENDING_TREND_CHECK_ENABLED": PENDING_TREND_CHECK_ENABLED,
    "PENDING_TREND_CHECK_POINTS":  PENDING_TREND_CHECK_POINTS,
    "PENDING_TREND_CHECK_ROUNDS":  PENDING_TREND_CHECK_ROUNDS,
    "TF_ACTIVE": copy.deepcopy(TF_ACTIVE),
    "TF_CURRENT": TF_CURRENT,
    "SWING_SUMMARY_MODE": SWING_SUMMARY_MODE,
    "SWING_PIVOT_LEFT": SWING_PIVOT_LEFT,
    "SWING_PIVOT_RIGHT": SWING_PIVOT_RIGHT,
    "SCALE_OUT_ENABLED": SCALE_OUT_ENABLED,
    "S1_ZONE_MODE": S1_ZONE_MODE,
    "S1_REJECTION_ENTRY_ENABLED": S1_REJECTION_ENTRY_ENABLED,
    # S14 sub-pattern toggles (runtime-resettable)
    "S14_SWEEP_SWING":    S14_SWEEP_SWING,
    "S14_ENGULF_SWING":   S14_ENGULF_SWING,
    "S14_SWEEP_RETURN":   S14_SWEEP_RETURN,
    "S14_FLIP_ENABLED":       S14_FLIP_ENABLED,
    "S14_ENGULF_BREAKEVEN":   S14_ENGULF_BREAKEVEN,
    "S14_RSI_DIV_ENABLED":    S14_RSI_DIV_ENABLED,
    # S15 config (runtime-resettable)
    "S15_USE_VAL_VAH":          S15_USE_VAL_VAH,
    "S15_LOOKBACK":             S15_LOOKBACK,
    "S15_MIN_RR":               S15_MIN_RR,
    "S15_TREND_FILTER":         S15_TREND_FILTER,
    "S15_STRICT_MODE":          S15_STRICT_MODE,
    "S15_LEVEL_COOLDOWN_BARS":  S15_LEVEL_COOLDOWN_BARS,
    "S15_RSI_FILTER":           S15_RSI_FILTER,
    # Scan / recheck flags
    "TREND_FILTER_SCAN_BLOCK":  TREND_FILTER_SCAN_BLOCK,
    "PDFIBOPLUS_ENABLED":       PDFIBOPLUS_ENABLED,
    "SHARED_TP_ENABLED":        SHARED_TP_ENABLED,
    "RECHECK_COMBINED_MODE":    RECHECK_COMBINED_MODE,
    "PENDING_RSI_RECHECK_MODE": PENDING_RSI_RECHECK_MODE,
    # SL Guard
    "SL_GUARD_ENABLED":           SL_GUARD_ENABLED,
    "SL_GUARD_COUNT":             SL_GUARD_COUNT,
    "SL_GUARD_NEAR_POINTS":       SL_GUARD_NEAR_POINTS,
    "SL_GUARD_LOSS_ENABLED":      SL_GUARD_LOSS_ENABLED,
    "SL_GUARD_LOSS_THRESHOLD":    SL_GUARD_LOSS_THRESHOLD,
    "SL_GUARD_CLOSE_ON_ACTIVATE": SL_GUARD_CLOSE_ON_ACTIVATE,
    "SL_GUARD_COMBINED_ENABLED":  SL_GUARD_COMBINED_ENABLED,
    "SL_GUARD_COMBINED_COUNT":    SL_GUARD_COMBINED_COUNT,
    "SL_GUARD_COMBINED_TFS":      copy.deepcopy(SL_GUARD_COMBINED_TFS),
    "SL_GUARD_GROUP_ENABLED":     SL_GUARD_GROUP_ENABLED,
    "SL_GUARD_GROUP_COUNT":       SL_GUARD_GROUP_COUNT,
    # S16 AMD x iFVG (runtime-resettable)
    "S16_ENTRY_MODE":        S16_ENTRY_MODE,
    "S16_MIN_RR":            S16_MIN_RR,
    "S16_SL_ATR_BUFFER":     S16_SL_ATR_BUFFER,
    "S16_MAX_RISK_ATR_MULT": S16_MAX_RISK_ATR_MULT,
    "S16_KZ_ONE_SHOT":       S16_KZ_ONE_SHOT,
    # S17 Sweep Sniper (runtime-resettable)
    "S17_SESSION_FILTER":      S17_SESSION_FILTER,
    "S17_PD_FILTER":           S17_PD_FILTER,
    "S17_TREND_FILTER":        S17_TREND_FILTER,
    "S17_ENTRY_MODE":          S17_ENTRY_MODE,
    "S17_RSI_BUY_MAX":         S17_RSI_BUY_MAX,
    "S17_RSI_SELL_MIN":        S17_RSI_SELL_MIN,
    "S17_TP_ATR_MULT":         S17_TP_ATR_MULT,
    "S17_SL_ATR_BUFFER":       S17_SL_ATR_BUFFER,
    "S17_MAX_RISK_ATR_MULT":   S17_MAX_RISK_ATR_MULT,
    "S17_LEVEL_COOLDOWN_BARS": S17_LEVEL_COOLDOWN_BARS,
    "S17_LIMIT_CANCEL_BARS":   S17_LIMIT_CANCEL_BARS,
    # S18 TJR / ICT Full-Confluence (runtime-resettable)
    "S18_SESSION_FILTER":    S18_SESSION_FILTER,
    "S18_RSI_FILTER":        S18_RSI_FILTER,
    "S18_ZONE_PREFER":       S18_ZONE_PREFER,
    "S18_ENTRY_MODE":        S18_ENTRY_MODE,
    "S18_MIN_RR":            S18_MIN_RR,
    # S19 ICT Advanced — Silver Bullet (runtime-resettable)
    "S19_SESSION_FILTER":    S19_SESSION_FILTER,
    "S19_P3_SESSION_SWEEP":  S19_P3_SESSION_SWEEP,
    "S19_USE_NDOG":          S19_USE_NDOG,
    "S19_ZONE_PREFER":       S19_ZONE_PREFER,
    "S19_MIN_RR":            S19_MIN_RR,
    # S20 All in 4s (runtime-resettable)
    "S20_ENABLED":             S20_ENABLED,
    "S20_5_ENABLED":           S20_5_ENABLED,
    "S20_5_COMPOUNDING_ENABLED": S20_5_COMPOUNDING_ENABLED,
    "S20_5_RISK_PCT":          S20_5_RISK_PCT,
    "S20_5_MAX_LOT":           S20_5_MAX_LOT,
    "S20_5_TF_ENABLED":        copy.deepcopy(S20_5_TF_ENABLED),
    "S20_6_FVG_ENABLED":       S20_6_FVG_ENABLED,
    "S20_TRIGGER_DEFECT":      S20_TRIGGER_DEFECT,
    "S20_TRIGGER_2L2H":        S20_TRIGGER_2L2H,
    "S20_TRIGGER_SOLID_CLEAR": S20_TRIGGER_SOLID_CLEAR,
    "S20_TRIGGER_FVG_OB":      S20_TRIGGER_FVG_OB,
    "S20_MODIFIER_MAGIC_NUM":  S20_MODIFIER_MAGIC_NUM,
    "S20_MODIFIER_SIGNIFICANT":S20_MODIFIER_SIGNIFICANT,
    "S20_MODIFIER_FIBO_CONF":  S20_MODIFIER_FIBO_CONF,
    "S20_MODIFIER_NO_BODY_BRK":S20_MODIFIER_NO_BODY_BRK,
    "S20_CANCEL_ON_2L":        S20_CANCEL_ON_2L,
    "S20_MIN_BODY_ATR_PCT":    S20_MIN_BODY_ATR_PCT,
    "S20_SL_BUFFER":           S20_SL_BUFFER,
    "S20_FIBO_TP_LEVEL":     S20_FIBO_TP_LEVEL,
    "S20_TREND_FILTER":      S20_TREND_FILTER,
    "S20_SESSION_FILTER":    S20_SESSION_FILTER,
    "S20_ENTRY_BUFFER":      S20_ENTRY_BUFFER,
    "S20_SL_2L2H":           S20_SL_2L2H,
    "S20_11_ENABLED":        S20_11_ENABLED,
    "S20_11_TF_ENABLED":     S20_11_TF_ENABLED,
    "S20_11_COMPOUNDING_ENABLED": S20_11_COMPOUNDING_ENABLED,
    "S20_11_RISK_PCT":       S20_11_RISK_PCT,
    "S20_11_MAX_LOT":        S20_11_MAX_LOT,
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
    
    # ── ล้างค่าจากการจูน Walk-Forward ด้วย (ถ้ามี) ──
    import os
    if os.path.exists("optimized_params.json"):
        try:
            os.remove("optimized_params.json")
            print("🗑️ Deleted optimized_params.json during config reset")
        except Exception as e:
            print(f"⚠️ Failed to delete optimized_params.json: {e}")
            try:
                from bot_log import log_error as _lerr
                _lerr("CONFIG_RESET_ERROR", f"delete optimized_params: {type(e).__name__}: {e}")
            except Exception:
                pass
            
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


# save_runtime_state เขียนไฟล์ทุก ~15s จาก main event loop thread (สังเกตจาก
# stall_trace.log: config.py save_runtime_state ติด top-of-stack 7/102 ครั้งตอน
# event loop ค้าง) → เขียนไฟล์ (disk I/O) ใน background thread แทน กัน I/O ช้า
# (เช่น antivirus scan, disk งานหนัก) มาแข็ง event loop ทั้งบอท
# _save_state_lock: best-effort กัน 2 thread เขียนไฟล์ทับกันพร้อมกัน (ถ้า save
# ครั้งก่อนยังไม่จบ ให้ skip ครั้งใหม่ไปเลย เดี๋ยวรอบ 15s ถัดไปจะ save ใหม่อยู่ดี)
_save_state_lock = threading.Lock()


def _write_state_to_disk(state: dict) -> None:
    try:
        tmp_path = STATE_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        last_error = None
        for attempt in range(5):
            try:
                os.replace(tmp_path, STATE_FILE)
                last_error = None
                break
            except PermissionError as e:
                last_error = e
                time.sleep(0.2 * (attempt + 1))
        if last_error is not None:
            raise last_error
    except Exception as e:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ save_runtime_state (disk write) error: {e}")
        try:
            from bot_log import log_error as _lerr
            _lerr("SAVE_STATE_ERROR", f"{type(e).__name__}: {e}")
        except Exception:
            pass
    finally:
        _save_state_lock.release()


def save_runtime_state():
    """บันทึก state สำคัญลงไฟล์เพื่อ restore หลัง restart"""
    try:
        from trailing import (
            fvg_order_tickets, pending_order_tf, position_tf, position_sid,
            position_pattern, position_trend_filter, position_zone_meta, position_forward_meta, _entry_state, _trail_state, _s8_fill_sl,
            _focus_frozen_side, _focus_suppress_until_flat, _fill_notified,
            _sl_guard_state, _sl_guard_combined, _sl_guard_group, _pdfiboplus_fill_state
        )
        # SL Guard state — กัน restart (stall) ล้างความจำ guard ก่อนครบเงื่อนไข unblock
        # _sl_guard_state key เป็น tuple (sym, tf, side) ต้องแปลงเป็น string ก่อนเก็บ JSON
        # snapshot ก่อน iterate ทุกตัว — กัน RuntimeError: dictionary changed size during iteration
        # (trailing.py อาจแก้ dict พร้อมกับ save_runtime_state ที่รัน ทุก 15s)
        _sl_guard_state_snap    = copy.deepcopy(_sl_guard_state)
        _pdfiboplus_fill_snap   = copy.deepcopy(_pdfiboplus_fill_state)
        sl_guard_state_serialized = {
            f"{k[0]}|{k[1]}|{k[2]}": dict(v) for k, v in _sl_guard_state_snap.items()
        }
        sl_guard_combined_serialized = copy.deepcopy(_sl_guard_combined)
        sl_guard_group_serialized    = copy.deepcopy(_sl_guard_group)
        # PD Fibo Plus round 2 wait state — กัน restart ล้าง state ระหว่างรอ round 2
        pdfiboplus_fill_state_serialized = {str(k): v for k, v in _pdfiboplus_fill_snap.items()}

        # S10 MTF armed states (per HTF) — กัน restart ตอน armed อยู่
        # snapshot ก่อน iterate — _armed_states ถูก pop/set บ่อยมากทุกรอบ scan (เหมือนจุดอื่นด้านบน)
        try:
            from strategy10 import _armed_states as _s10_armed
            _s10_armed_snap = copy.deepcopy(_s10_armed)
            s10_armed_serialized = {k: dict(v) for k, v in _s10_armed_snap.items()}
        except Exception:
            s10_armed_serialized = {}

        # S10 last_fired_armed_at — กัน restart ทำให้ guard ป้องกัน duplicate fire หาย
        try:
            from strategy10 import _last_fired_armed_at as _s10_last_fired
            s10_last_fired_serialized = dict(_s10_last_fired)
        except Exception:
            s10_last_fired_serialized = {}

        # S16 state (AMD x iFVG) — กัน restart ตอนคำนวณเอเชียได้แล้ว
        try:
            from strategy16 import s16_state
            s16_state_serialized = copy.deepcopy(s16_state)
        except Exception:
            s16_state_serialized = {}

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
            "pdfiboplus_enabled": PDFIBOPLUS_ENABLED,
            "shared_tp_enabled": SHARED_TP_ENABLED,
            "s20_enabled": S20_ENABLED,
            "s20_5_enabled": S20_5_ENABLED,
            "s20_5_compounding_enabled": S20_5_COMPOUNDING_ENABLED,
            "s20_5_risk_pct": S20_5_RISK_PCT,
            "s20_5_max_lot": S20_5_MAX_LOT,
            "s20_5_tf_enabled": S20_5_TF_ENABLED,
            "s20_6_fvg_enabled": S20_6_FVG_ENABLED,
            "s20_6_tf_enabled": S20_6_TF_ENABLED,
            "s20_6_session_filter": S20_6_SESSION_FILTER,
            "s20_6_trend_filter": S20_6_TREND_FILTER,
            "s20_6_entry_buffer": S20_6_ENTRY_BUFFER,
            "s20_6_compounding_enabled": S20_6_COMPOUNDING_ENABLED,
            "s20_6_risk_pct": S20_6_RISK_PCT,
            "s20_6_max_lot": S20_6_MAX_LOT,
            "s20_7_enabled": S20_7_ENABLED,
            "s20_8_enabled": S20_8_ENABLED,
            "s20_8_compounding_enabled": S20_8_COMPOUNDING_ENABLED,
            "s20_8_risk_pct": S20_8_RISK_PCT,
            "s20_8_max_lot": S20_8_MAX_LOT,
            "s20_9_enabled": S20_9_ENABLED,
            "s20_10_enabled": S20_10_ENABLED,
            "s20_10_compounding_enabled": S20_10_COMPOUNDING_ENABLED,
            "s20_10_risk_pct": S20_10_RISK_PCT,
            "s20_10_max_lot": S20_10_MAX_LOT,
            "s20_10_use_psychological_numbers": S20_10_USE_PSYCHOLOGICAL_NUMBERS,
            "s20_11_enabled": S20_11_ENABLED,
            "s20_11_tf_enabled": S20_11_TF_ENABLED,
            "s20_11_compounding_enabled": S20_11_COMPOUNDING_ENABLED,
            "s20_11_risk_pct": S20_11_RISK_PCT,
            "s20_11_max_lot": S20_11_MAX_LOT,
            "s20_12_enabled": S20_12_ENABLED,
            "s20_12_tf_enabled": S20_12_TF_ENABLED,
            "s20_12_compounding_enabled": S20_12_COMPOUNDING_ENABLED,
            "s20_12_risk_pct": S20_12_RISK_PCT,
            "s20_12_max_lot": S20_12_MAX_LOT,
            "s20_12_session_filter": S20_12_SESSION_FILTER,
            "recheck_combined_mode": RECHECK_COMBINED_MODE,
            "near_approach_cancel_enabled": NEAR_APPROACH_CANCEL_ENABLED,
            "near_approach_cancel_points": NEAR_APPROACH_CANCEL_POINTS,
            "pending_trend_check_enabled": PENDING_TREND_CHECK_ENABLED,
            "pending_trend_check_points":  PENDING_TREND_CHECK_POINTS,
            "pending_trend_check_rounds":  PENDING_TREND_CHECK_ROUNDS,
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
            "sweep_filter_enabled": SWEEP_FILTER_ENABLED,
            "sweep_filter_rsi_div_enabled": SWEEP_FILTER_RSI_DIV_ENABLED,
            "trend_filter_mode": TREND_FILTER_MODE,
            "swing_summary_mode": SWING_SUMMARY_MODE,
            "swing_pivot_left": SWING_PIVOT_LEFT,
            "swing_pivot_right": SWING_PIVOT_RIGHT,
            "crt_bar_mode": CRT_BAR_MODE,
            "s1_zone_mode": S1_ZONE_MODE,
            "s1_rejection_entry_enabled": S1_REJECTION_ENTRY_ENABLED,
            "crt_sweep_depth_pct": CRT_SWEEP_DEPTH_PCT,
            "crt_entry_mode": CRT_ENTRY_MODE,
            "crt_wait_htf_close": CRT_WAIT_HTF_CLOSE,
            "crt_parent_min_body_pct": CRT_PARENT_MIN_BODY_PCT,
            "crt_sweep_contain_enabled": CRT_SWEEP_CONTAIN_ENABLED,
            "crt_sweep_close_max_pct": CRT_SWEEP_CLOSE_MAX_PCT,
            "s10_retry_after_sl": S10_RETRY_AFTER_SL,
            "s14_sweep_swing":      S14_SWEEP_SWING,
            "s14_engulf_swing":     S14_ENGULF_SWING,
            "s14_sweep_return":     S14_SWEEP_RETURN,
            "s14_engulf_breakeven": S14_ENGULF_BREAKEVEN,
            "s14_rsi_div_enabled":   S14_RSI_DIV_ENABLED,
            "s10_armed_states": s10_armed_serialized,
            "rsi9_plot_bullish": RSI9_PLOT_BULLISH,
            "rsi9_plot_hidden_bullish": RSI9_PLOT_HIDDEN_BULLISH,
            "rsi9_plot_bearish": RSI9_PLOT_BEARISH,
            "rsi9_plot_hidden_bearish": RSI9_PLOT_HIDDEN_BEARISH,
            "entry_candle_enabled": ENTRY_CANDLE_ENABLED,
            "opposite_order_enabled": OPPOSITE_ORDER_ENABLED,
            "limit_sweep": LIMIT_SWEEP,
            "daily_loss_limit_enabled": DAILY_LOSS_LIMIT_ENABLED,
            "daily_loss_limit_usd": DAILY_LOSS_LIMIT_USD,
            "daily_stats": daily_stats,
            "daily_loss_tripped": daily_loss_tripped,
            "daily_summary_enabled": DAILY_SUMMARY_ENABLED,
            "risk_percent_enabled": RISK_PERCENT_ENABLED,
            "risk_percent": RISK_PERCENT,
            "risk_max_lot": RISK_MAX_LOT,
            "watchdog_enabled": WATCHDOG_ENABLED,
            "delay_sl_mode": DELAY_SL_MODE,
            "fvg_normal": FVG_NORMAL,
            "fvg_parallel": FVG_PARALLEL,
            "s2_adjacent_block_enabled": S2_ADJACENT_BLOCK_ENABLED,
            "s3_adjacent_block_enabled": S3_ADJACENT_BLOCK_ENABLED,
            "s2_s3_chain_link_enabled": S2_S3_CHAIN_LINK_ENABLED,
            "s2_s3_chain_swing_cancel_enabled": S2_S3_CHAIN_SWING_CANCEL_ENABLED,
            "s2_s3_chain_swing_cancel_tf": S2_S3_CHAIN_SWING_CANCEL_TF,
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
            "sl_guard_state": sl_guard_state_serialized,
            "sl_guard_combined_state": sl_guard_combined_serialized,
            "sl_guard_group_state": sl_guard_group_serialized,
            "pdfiboplus_fill_state": pdfiboplus_fill_state_serialized,
            "s10_last_fired_armed_at": s10_last_fired_serialized,
            # snapshot shared dicts ก่อน serialize — กัน race กับ trailing.py
            "last_traded_per_tf":     copy.deepcopy(last_traded_per_tf),
            "last_traded_sid_tf":     copy.deepcopy(last_traded_sid_tf),
            "pending_order_tf":       copy.deepcopy(pending_order_tf),
            "position_tf":            copy.deepcopy(position_tf),
            "position_sid":           copy.deepcopy(position_sid),
            "position_pattern":       copy.deepcopy(position_pattern),
            "position_trend_filter":  copy.deepcopy(position_trend_filter),
            "position_zone_meta":     copy.deepcopy(position_zone_meta),
            "position_forward_meta":  copy.deepcopy(position_forward_meta),
            "entry_state":            copy.deepcopy(_entry_state),
            "trail_state":            copy.deepcopy(_trail_state),
            "fvg_order_tickets":      copy.deepcopy(fvg_order_tickets),
            "s8_fill_sl":             copy.deepcopy(_s8_fill_sl),
            "trail_sl_frozen_side":   _focus_frozen_side.get("trail_sl"),
            "entry_candle_frozen_side": _focus_frozen_side.get("entry_candle"),
            "trail_sl_focus_suppress_until_flat": bool(_focus_suppress_until_flat.get("trail_sl", False)),
            "entry_candle_focus_suppress_until_flat": bool(_focus_suppress_until_flat.get("entry_candle", False)),
            "scale_out_enabled":      SCALE_OUT_ENABLED,
            "scale_out_state":        {str(k): v for k, v in copy.deepcopy(scale_out_state).items()},
            # S15 Volume Profile POC
            "s15_use_val_vah":          S15_USE_VAL_VAH,
            "s15_lookback":             S15_LOOKBACK,
            "s15_min_rr":               S15_MIN_RR,
            "s15_trend_filter":         S15_TREND_FILTER,
            "s15_strict_mode":          S15_STRICT_MODE,
            "s15_level_cooldown_bars":  S15_LEVEL_COOLDOWN_BARS,
            "s15_rsi_filter":           S15_RSI_FILTER,
            # S16 AMD x iFVG
            "s16_state":                s16_state_serialized,
            # S20 All in 4s
            "s20_enabled":              S20_ENABLED,
            "s20_trigger_defect":       S20_TRIGGER_DEFECT,
            "s20_trigger_2l2h":         S20_TRIGGER_2L2H,
            "s20_trigger_solid_clear":  S20_TRIGGER_SOLID_CLEAR,
            "s20_trigger_fvg_ob":       S20_TRIGGER_FVG_OB,
            "s20_modifier_magic_num":   S20_MODIFIER_MAGIC_NUM,
            "s20_modifier_significant": S20_MODIFIER_SIGNIFICANT,
            "s20_modifier_fibo_conf":   S20_MODIFIER_FIBO_CONF,
            "s20_modifier_no_body_brk": S20_MODIFIER_NO_BODY_BRK,
            "s20_cancel_on_2l":         S20_CANCEL_ON_2L,
            "s20_min_body_atr_pct":     S20_MIN_BODY_ATR_PCT,
            "s20_sl_buffer":            S20_SL_BUFFER,
            "s20_fibo_tp_level":        S20_FIBO_TP_LEVEL,
            "s20_trend_filter":         S20_TREND_FILTER,
            "s20_session_filter":       S20_SESSION_FILTER,
            "s20_entry_buffer":         S20_ENTRY_BUFFER,
            "s20_sl_2l2h":              S20_SL_2L2H,
            # fill_notified — กัน ENTRY_FILL ซ้ำหลัง restart
            "fill_notified":            list(_fill_notified.keys()),
        }

        # ตัว state dict สร้างเสร็จแล้ว (in-memory, เร็ว) — ส่ง disk write ไป background
        # thread กัน I/O ช้าแข็ง event loop (ดูคอมเมนต์ _write_state_to_disk ด้านบน)
        if _save_state_lock.acquire(blocking=False):
            threading.Thread(
                target=_write_state_to_disk, args=(state,), daemon=True, name="SaveStateWriter"
            ).start()
        # else: save รอบก่อนยังเขียนไม่จบ → skip รอบนี้ (รอบ 15s ถัดไป save ใหม่อยู่ดี)
    except Exception as e:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ save_runtime_state error: {e}")
        try:
            from bot_log import log_error as _lerr
            _lerr("SAVE_STATE_ERROR", f"{type(e).__name__}: {e}")
        except Exception:
            pass


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
            _focus_frozen_side, _focus_suppress_until_flat, _fill_notified
        )

        # SL Guard state — restore ตรงๆ (ไม่เช็ค staleness เพราะเงื่อนไข unblock
        # ใช้ swing confirm ซึ่งกินเวลาได้หลายชั่วโมง ไม่ใช่ timer คงที่)
        try:
            import trailing as _trailing_mod
            saved_sgs = state.get("sl_guard_state", {})
            if isinstance(saved_sgs, dict):
                _trailing_mod._sl_guard_state.clear()
                for k, v in saved_sgs.items():
                    parts = k.split("|")
                    if len(parts) == 3 and isinstance(v, dict):
                        _trailing_mod._sl_guard_state[(parts[0], parts[1], parts[2])] = v
            saved_sgc = state.get("sl_guard_combined_state", {})
            if isinstance(saved_sgc, dict):
                _trailing_mod._sl_guard_combined.clear()
                _trailing_mod._sl_guard_combined.update(saved_sgc)
            saved_sgg = state.get("sl_guard_group_state", {})
            if isinstance(saved_sgg, dict):
                _trailing_mod._sl_guard_group.clear()
                _trailing_mod._sl_guard_group.update(saved_sgg)
            # PD Fibo Plus round 2 wait state — key ticket เก็บเป็น string ต้องแปลงกลับเป็น int
            saved_pdfp = state.get("pdfiboplus_fill_state", {})
            if isinstance(saved_pdfp, dict):
                _trailing_mod._pdfiboplus_fill_state.clear()
                for k, v in saved_pdfp.items():
                    try:
                        _trailing_mod._pdfiboplus_fill_state[int(k)] = v
                    except (TypeError, ValueError):
                        continue
        except Exception:
            pass

        # S10 last_fired_armed_at — กัน duplicate fire ซ้ำ HTF bar เดิมหลัง restart
        try:
            from strategy10 import _last_fired_armed_at as _s10_last_fired
            saved_s10_last_fired = state.get("s10_last_fired_armed_at", {})
            if isinstance(saved_s10_last_fired, dict):
                _s10_last_fired.clear()
                _s10_last_fired.update(saved_s10_last_fired)
        except Exception:
            pass

        saved_symbol = state.get("symbol")
        if saved_symbol and saved_symbol != SYMBOL:
            set_runtime_symbol(saved_symbol)

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
        global TREND_FILTER_SCAN_BLOCK, PDFIBOPLUS_ENABLED, SHARED_TP_ENABLED, RECHECK_COMBINED_MODE
        global NEAR_APPROACH_CANCEL_ENABLED, NEAR_APPROACH_CANCEL_POINTS
        global PENDING_TREND_CHECK_ENABLED, PENDING_TREND_CHECK_POINTS, PENDING_TREND_CHECK_ROUNDS
        global TRAIL_SL_IMMEDIATE, LIMIT_SWEEP
        global DELAY_SL_MODE
        global FVG_NORMAL, FVG_PARALLEL
        global S2_ADJACENT_BLOCK_ENABLED, S3_ADJACENT_BLOCK_ENABLED, S2_S3_CHAIN_LINK_ENABLED
        global S2_S3_CHAIN_SWING_CANCEL_ENABLED, S2_S3_CHAIN_SWING_CANCEL_TF
        global TRAIL_SL_ENABLED, ENTRY_CANDLE_ENABLED, OPPOSITE_ORDER_ENABLED
        global TRAIL_SL_FOCUS_NEW_ENABLED, TRAIL_SL_FOCUS_NEW_POINTS, TRAIL_SL_FOCUS_NEW_TF_MODE
        global TRAIL_SL_REVERSAL_OVERRIDE_ENABLED
        global ENTRY_CANDLE_FOCUS_NEW_ENABLED, ENTRY_CANDLE_FOCUS_NEW_POINTS, ENTRY_CANDLE_FOCUS_NEW_TF_MODE
        global TREND_FILTER_HIGHER_TF_ENABLED, TREND_FILTER_HIGHER_TF, TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED
        global TREND_FILTER_SIDEWAY_HHLL
        global SWEEP_FILTER_ENABLED, SWEEP_FILTER_RSI_DIV_ENABLED
        global TREND_FILTER_MODE
        global SWING_SUMMARY_MODE, SWING_PIVOT_LEFT, SWING_PIVOT_RIGHT
        global S1_ZONE_MODE, S1_REJECTION_ENTRY_ENABLED
        global CRT_BAR_MODE, CRT_SWEEP_DEPTH_PCT, CRT_ENTRY_MODE, CRT_WAIT_HTF_CLOSE, CRT_PARENT_MIN_BODY_PCT
        global CRT_SWEEP_CONTAIN_ENABLED, CRT_SWEEP_CLOSE_MAX_PCT
        global S10_RETRY_AFTER_SL
        global S14_SWEEP_SWING, S14_ENGULF_SWING, S14_SWEEP_RETURN, S14_ENGULF_BREAKEVEN, S14_RSI_DIV_ENABLED
        global RSI9_PLOT_BULLISH, RSI9_PLOT_HIDDEN_BULLISH, RSI9_PLOT_BEARISH, RSI9_PLOT_HIDDEN_BEARISH
        global S20_ENABLED, S20_SUB_CONFIG, S20_MIN_BODY_ATR_PCT, S20_SL_BUFFER, S20_FIBO_TP_LEVEL, S20_TREND_FILTER, S20_SESSION_FILTER, S20_ENTRY_BUFFER, S20_SL_2L2H
        global S20_5_ENABLED, S20_5_COMPOUNDING_ENABLED, S20_5_RISK_PCT, S20_5_MAX_LOT, S20_5_TF_ENABLED
        global S20_6_FVG_ENABLED, S20_6_TF_ENABLED, S20_6_SESSION_FILTER, S20_6_TREND_FILTER, S20_6_ENTRY_BUFFER, S20_6_COMPOUNDING_ENABLED, S20_6_RISK_PCT, S20_6_MAX_LOT
        global S20_7_ENABLED, S20_8_ENABLED
        global S20_8_COMPOUNDING_ENABLED, S20_8_RISK_PCT, S20_8_MAX_LOT
        global S20_9_ENABLED, S20_10_ENABLED, S20_10_COMPOUNDING_ENABLED, S20_10_RISK_PCT, S20_10_MAX_LOT, S20_10_USE_PSYCHOLOGICAL_NUMBERS
        global S20_11_ENABLED, S20_11_COMPOUNDING_ENABLED, S20_11_RISK_PCT, S20_11_MAX_LOT, S20_11_TF_ENABLED
        global S20_12_ENABLED, S20_12_COMPOUNDING_ENABLED, S20_12_RISK_PCT, S20_12_MAX_LOT, S20_12_TF_ENABLED, S20_12_SESSION_FILTER
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
        PDFIBOPLUS_ENABLED = bool(state.get("pdfiboplus_enabled", PDFIBOPLUS_ENABLED))
        SHARED_TP_ENABLED = bool(state.get("shared_tp_enabled", SHARED_TP_ENABLED))
        S20_ENABLED = bool(state.get("s20_enabled", True))
        S20_5_ENABLED = bool(state.get("s20_5_enabled", S20_5_ENABLED))
        S20_5_COMPOUNDING_ENABLED = bool(state.get("s20_5_compounding_enabled", S20_5_COMPOUNDING_ENABLED))
        S20_5_RISK_PCT = float(state.get("s20_5_risk_pct", S20_5_RISK_PCT))
        S20_5_MAX_LOT = float(state.get("s20_5_max_lot", S20_5_MAX_LOT))
        s20_5_tf = state.get("s20_5_tf_enabled")
        if isinstance(s20_5_tf, dict):
            S20_5_TF_ENABLED.update(s20_5_tf)
        S20_6_FVG_ENABLED = bool(state.get("s20_6_fvg_enabled", S20_6_FVG_ENABLED))
        saved_s20_6_tf = state.get("s20_6_tf_enabled")
        if saved_s20_6_tf and isinstance(saved_s20_6_tf, dict):
            S20_6_TF_ENABLED.update(saved_s20_6_tf)
        S20_6_SESSION_FILTER = bool(state.get("s20_6_session_filter", S20_6_SESSION_FILTER))
        S20_6_TREND_FILTER = bool(state.get("s20_6_trend_filter", S20_6_TREND_FILTER))
        S20_6_ENTRY_BUFFER = float(state.get("s20_6_entry_buffer", S20_6_ENTRY_BUFFER))
        S20_6_COMPOUNDING_ENABLED = bool(state.get("s20_6_compounding_enabled", S20_6_COMPOUNDING_ENABLED))
        S20_6_RISK_PCT = float(state.get("s20_6_risk_pct", S20_6_RISK_PCT))
        S20_6_MAX_LOT = float(state.get("s20_6_max_lot", S20_6_MAX_LOT))
        S20_7_ENABLED = bool(state.get("s20_7_enabled", S20_7_ENABLED))
        S20_8_ENABLED = bool(state.get("s20_8_enabled", S20_8_ENABLED))
        S20_8_COMPOUNDING_ENABLED = bool(state.get("s20_8_compounding_enabled", S20_8_COMPOUNDING_ENABLED))
        S20_8_RISK_PCT = float(state.get("s20_8_risk_pct", S20_8_RISK_PCT))
        S20_8_MAX_LOT = float(state.get("s20_8_max_lot", S20_8_MAX_LOT))
        S20_9_ENABLED = bool(state.get("s20_9_enabled", S20_9_ENABLED))
        S20_10_ENABLED = bool(state.get("s20_10_enabled", S20_10_ENABLED))
        S20_10_COMPOUNDING_ENABLED = bool(state.get("s20_10_compounding_enabled", S20_10_COMPOUNDING_ENABLED))
        S20_10_RISK_PCT = float(state.get("s20_10_risk_pct", S20_10_RISK_PCT))
        S20_10_MAX_LOT = float(state.get("s20_10_max_lot", S20_10_MAX_LOT))
        S20_10_USE_PSYCHOLOGICAL_NUMBERS = bool(state.get("s20_10_use_psychological_numbers", S20_10_USE_PSYCHOLOGICAL_NUMBERS))
        S20_11_ENABLED = bool(state.get("s20_11_enabled", S20_11_ENABLED))
        saved_s20_11_tf = state.get("s20_11_tf_enabled", {})
        if isinstance(saved_s20_11_tf, dict):
            for tf_name in S20_11_TF_ENABLED:
                if tf_name in saved_s20_11_tf:
                    S20_11_TF_ENABLED[tf_name] = bool(saved_s20_11_tf[tf_name])
        S20_11_COMPOUNDING_ENABLED = bool(state.get("s20_11_compounding_enabled", S20_11_COMPOUNDING_ENABLED))
        saved_s20_11_risk = state.get("s20_11_risk_pct")
        if isinstance(saved_s20_11_risk, (int, float)) and saved_s20_11_risk > 0:
            S20_11_RISK_PCT = float(saved_s20_11_risk)
        saved_s20_11_max = state.get("s20_11_max_lot")
        if isinstance(saved_s20_11_max, (int, float)) and saved_s20_11_max > 0:
            S20_11_MAX_LOT = float(saved_s20_11_max)

        S20_12_ENABLED = bool(state.get("s20_12_enabled", S20_12_ENABLED))
        saved_s20_12_tf = state.get("s20_12_tf_enabled", {})
        if isinstance(saved_s20_12_tf, dict):
            for tf_name in S20_12_TF_ENABLED:
                if tf_name in saved_s20_12_tf:
                    S20_12_TF_ENABLED[tf_name] = bool(saved_s20_12_tf[tf_name])
        S20_12_COMPOUNDING_ENABLED = bool(state.get("s20_12_compounding_enabled", S20_12_COMPOUNDING_ENABLED))
        saved_s20_12_risk = state.get("s20_12_risk_pct")
        if isinstance(saved_s20_12_risk, (int, float)) and saved_s20_12_risk > 0:
            S20_12_RISK_PCT = float(saved_s20_12_risk)
        saved_s20_12_max = state.get("s20_12_max_lot")
        if isinstance(saved_s20_12_max, (int, float)) and saved_s20_12_max > 0:
            S20_12_MAX_LOT = float(saved_s20_12_max)
        S20_12_SESSION_FILTER = bool(state.get("s20_12_session_filter", S20_12_SESSION_FILTER))

        S20_11_ENABLED = bool(state.get("s20_11_enabled", S20_11_ENABLED))
        S20_11_TF_ENABLED = state.get("s20_11_tf_enabled", S20_11_TF_ENABLED)
        S20_11_COMPOUNDING_ENABLED = bool(state.get("s20_11_compounding_enabled", S20_11_COMPOUNDING_ENABLED))
        S20_11_RISK_PCT = float(state.get("s20_11_risk_pct", S20_11_RISK_PCT))
        S20_11_MAX_LOT = float(state.get("s20_11_max_lot", S20_11_MAX_LOT))
        saved_s20_sub = state.get("s20_sub_config")
        if isinstance(saved_s20_sub, dict):
            S20_SUB_CONFIG.update(saved_s20_sub)
        saved_s20_min_body = state.get("s20_min_body_atr_pct")
        if isinstance(saved_s20_min_body, (float, int)):
            S20_MIN_BODY_ATR_PCT = float(saved_s20_min_body)
        saved_s20_sl_buf = state.get("s20_sl_buffer")
        if isinstance(saved_s20_sl_buf, (float, int)):
            S20_SL_BUFFER = float(saved_s20_sl_buf)
        saved_s20_fibo_tp = state.get("s20_fibo_tp_level")
        if isinstance(saved_s20_fibo_tp, (float, int)):
            S20_FIBO_TP_LEVEL = float(saved_s20_fibo_tp)
        S20_TREND_FILTER = bool(state.get("s20_trend_filter", S20_TREND_FILTER))
        S20_SESSION_FILTER = bool(state.get("s20_session_filter", S20_SESSION_FILTER))
        
        saved_s20_entry_buf = state.get("s20_entry_buffer")
        if saved_s20_entry_buf is not None:
            S20_ENTRY_BUFFER = float(saved_s20_entry_buf)
            
        saved_s20_sl_2l2h = state.get("s20_sl_2l2h")
        if saved_s20_sl_2l2h is not None:
            S20_SL_2L2H = float(saved_s20_sl_2l2h)
        RECHECK_COMBINED_MODE = bool(state.get("recheck_combined_mode", RECHECK_COMBINED_MODE))
        NEAR_APPROACH_CANCEL_ENABLED = bool(state.get("near_approach_cancel_enabled", NEAR_APPROACH_CANCEL_ENABLED))
        saved_nac_pts = state.get("near_approach_cancel_points")
        if saved_nac_pts is not None:
            NEAR_APPROACH_CANCEL_POINTS = int(saved_nac_pts)
        PENDING_TREND_CHECK_ENABLED = bool(state.get("pending_trend_check_enabled", PENDING_TREND_CHECK_ENABLED))
        saved_ptc_pts = state.get("pending_trend_check_points")
        if saved_ptc_pts is not None:
            PENDING_TREND_CHECK_POINTS = int(saved_ptc_pts)
        saved_ptc_rounds = state.get("pending_trend_check_rounds")
        if saved_ptc_rounds is not None and int(saved_ptc_rounds) in (1, 2):
            PENDING_TREND_CHECK_ROUNDS = int(saved_ptc_rounds)
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
        SWEEP_FILTER_ENABLED = bool(
            state.get("sweep_filter_enabled", state.get("trend_filter_sweep_enabled", SWEEP_FILTER_ENABLED))
        )
        SWEEP_FILTER_RSI_DIV_ENABLED = bool(
            state.get("sweep_filter_rsi_div_enabled", SWEEP_FILTER_RSI_DIV_ENABLED)
        )
        S14_RSI_DIV_ENABLED = bool(
            state.get("s14_rsi_div_enabled", S14_RSI_DIV_ENABLED)
        )
        saved_tf_mode = state.get("trend_filter_mode")
        if saved_tf_mode in ("basic", "breakout"):
            TREND_FILTER_MODE = saved_tf_mode
        saved_s1_zone_mode = state.get("s1_zone_mode")
        if saved_s1_zone_mode in ("zone", "normal", "swing"):
            S1_ZONE_MODE = saved_s1_zone_mode
        S1_REJECTION_ENTRY_ENABLED = bool(state.get("s1_rejection_entry_enabled", S1_REJECTION_ENTRY_ENABLED))
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
        CRT_WAIT_HTF_CLOSE = bool(state.get("crt_wait_htf_close", CRT_WAIT_HTF_CLOSE))
        S10_RETRY_AFTER_SL = bool(state.get("s10_retry_after_sl", S10_RETRY_AFTER_SL))
        S14_SWEEP_SWING   = bool(state.get("s14_sweep_swing",   S14_SWEEP_SWING))
        S14_ENGULF_SWING  = bool(state.get("s14_engulf_swing",  S14_ENGULF_SWING))
        S14_SWEEP_RETURN      = bool(state.get("s14_sweep_return",      S14_SWEEP_RETURN))
        S14_ENGULF_BREAKEVEN  = bool(state.get("s14_engulf_breakeven",  S14_ENGULF_BREAKEVEN))
        try:
            saved_crt_body = float(state.get("crt_parent_min_body_pct", CRT_PARENT_MIN_BODY_PCT))
            if 0.0 <= saved_crt_body <= 1.0:
                CRT_PARENT_MIN_BODY_PCT = saved_crt_body
        except Exception:
            pass
        CRT_SWEEP_CONTAIN_ENABLED = bool(state.get("crt_sweep_contain_enabled", CRT_SWEEP_CONTAIN_ENABLED))
        try:
            saved_crt_close_pct = float(state.get("crt_sweep_close_max_pct", CRT_SWEEP_CLOSE_MAX_PCT))
            if 0.0 <= saved_crt_close_pct <= 1.0:
                CRT_SWEEP_CLOSE_MAX_PCT = saved_crt_close_pct
        except Exception:
            pass
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
        # ── Daily Loss Limit / Summary / Risk Lot / Watchdog ──
        global DAILY_LOSS_LIMIT_ENABLED, DAILY_LOSS_LIMIT_USD, daily_loss_tripped
        global DAILY_SUMMARY_ENABLED, RISK_PERCENT_ENABLED, RISK_PERCENT, RISK_MAX_LOT
        global WATCHDOG_ENABLED
        DAILY_LOSS_LIMIT_ENABLED = bool(state.get("daily_loss_limit_enabled", DAILY_LOSS_LIMIT_ENABLED))
        saved_dll_usd = state.get("daily_loss_limit_usd")
        if isinstance(saved_dll_usd, (int, float)) and saved_dll_usd > 0:
            DAILY_LOSS_LIMIT_USD = float(saved_dll_usd)
        DAILY_SUMMARY_ENABLED = bool(state.get("daily_summary_enabled", DAILY_SUMMARY_ENABLED))
        RISK_PERCENT_ENABLED = bool(state.get("risk_percent_enabled", RISK_PERCENT_ENABLED))
        saved_risk_pct = state.get("risk_percent")
        if isinstance(saved_risk_pct, (int, float)) and saved_risk_pct > 0:
            RISK_PERCENT = float(saved_risk_pct)
        saved_risk_max = state.get("risk_max_lot")
        if isinstance(saved_risk_max, (int, float)) and saved_risk_max > 0:
            RISK_MAX_LOT = float(saved_risk_max)
        WATCHDOG_ENABLED = bool(state.get("watchdog_enabled", WATCHDOG_ENABLED))
        # daily_stats — restore เฉพาะถ้ายังเป็นวันเดียวกัน (BKK) มิฉะนั้น roll ใหม่
        saved_daily = state.get("daily_stats")
        if isinstance(saved_daily, dict) and saved_daily.get("date") == _today_bkk():
            daily_stats.update(saved_daily)
            daily_loss_tripped = bool(state.get("daily_loss_tripped", False))
        else:
            _roll_daily_stats()
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
        S2_ADJACENT_BLOCK_ENABLED = bool(state.get("s2_adjacent_block_enabled", S2_ADJACENT_BLOCK_ENABLED))
        S3_ADJACENT_BLOCK_ENABLED = bool(state.get("s3_adjacent_block_enabled", S3_ADJACENT_BLOCK_ENABLED))
        S2_S3_CHAIN_LINK_ENABLED = bool(state.get("s2_s3_chain_link_enabled", S2_S3_CHAIN_LINK_ENABLED))
        if (S2_ADJACENT_BLOCK_ENABLED or S3_ADJACENT_BLOCK_ENABLED) and S2_S3_CHAIN_LINK_ENABLED:
            # safety: chain-link ใช้ได้ก็ต่อเมื่อปิด adjacent-block ทั้งคู่ — ถ้า state
            # ที่โหลดมาขัดกัน (เช่น restore จาก backup เก่า) ให้ปิด chain-link ไว้ก่อน
            S2_S3_CHAIN_LINK_ENABLED = False
        S2_S3_CHAIN_SWING_CANCEL_ENABLED = bool(state.get("s2_s3_chain_swing_cancel_enabled", S2_S3_CHAIN_SWING_CANCEL_ENABLED))
        saved_s2cs_tf = state.get("s2_s3_chain_swing_cancel_tf", {})
        if isinstance(saved_s2cs_tf, dict):
            for tf_name in S2_S3_CHAIN_SWING_CANCEL_TF:
                if tf_name in saved_s2cs_tf:
                    S2_S3_CHAIN_SWING_CANCEL_TF[tf_name] = bool(saved_s2cs_tf[tf_name])

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
        global S15_TREND_FILTER, S15_STRICT_MODE, S15_LEVEL_COOLDOWN_BARS, S15_RSI_FILTER
        S15_USE_VAL_VAH = bool(state.get("s15_use_val_vah", S15_USE_VAL_VAH))
        saved_s15_lb = state.get("s15_lookback")
        if saved_s15_lb is not None:
            S15_LOOKBACK = max(30, int(saved_s15_lb))
        saved_s15_rr = state.get("s15_min_rr")
        if saved_s15_rr is not None:
            S15_MIN_RR = max(0.5, float(saved_s15_rr))
        if "s15_trend_filter" in state:
            S15_TREND_FILTER = bool(state["s15_trend_filter"])
        if "s15_strict_mode" in state:
            S15_STRICT_MODE = bool(state["s15_strict_mode"])
        saved_s15_cd = state.get("s15_level_cooldown_bars")
        if saved_s15_cd is not None:
            S15_LEVEL_COOLDOWN_BARS = max(1, int(saved_s15_cd))
        if "s15_rsi_filter" in state:
            S15_RSI_FILTER = bool(state["s15_rsi_filter"])

        # S16 state (AMD x iFVG)
        try:
            from strategy16 import s16_state
            saved_s16_state = state.get("s16_state", {})
            if isinstance(saved_s16_state, dict):
                s16_state.clear()
                s16_state.update(saved_s16_state)
        except Exception as e:
            print(f"⚠️ restore_runtime_state S16 error: {e}")
            try:
                from bot_log import log_error as _lerr
                _lerr("RESTORE_STATE_ERROR", f"S16: {type(e).__name__}: {e}")
            except Exception:
                pass

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

        # Restore _fill_notified เฉพาะ ticket ที่ยังเปิดอยู่ใน MT5
        # ป้องกัน ENTRY_FILL ซ้ำหลัง restart สำหรับ position ที่ fill ไปแล้ว
        saved_fill_notified = state.get("fill_notified", [])
        if isinstance(saved_fill_notified, list):
            for t in saved_fill_notified:
                try:
                    tk = int(t)
                except (TypeError, ValueError):
                    continue
                if tk in open_pos_tickets:
                    _fill_notified[tk] = True

        for feature_key, state_key in (
            ("trail_sl", "trail_sl_frozen_side"),
            ("entry_candle", "entry_candle_frozen_side"),
        ):
            saved_side = state.get(state_key)
            _focus_frozen_side[feature_key] = saved_side if saved_side in ("BUY", "SELL") else None
        for feature_key, state_key in (
            ("trail_sl", "trail_sl_focus_suppress_until_flat"),
            ("entry_candle", "entry_candle_focus_suppress_until_flat"),
        ):
            _focus_suppress_until_flat[feature_key] = bool(state.get(state_key, False))

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

# ============================================================
#  Walk-Forward Optimization Loader
# ============================================================
import os
import json
OPTIMIZED_PARAMS_FILE = "optimized_params.json"
if os.path.exists(OPTIMIZED_PARAMS_FILE):
    try:
        with open(OPTIMIZED_PARAMS_FILE, "r", encoding="utf-8") as _f:
            _opt = json.load(_f)
            for _k, _v in _opt.items():
                if _k not in globals():
                    continue
                # ห้ามทับ function/class/module — กัน WFO เผลอเขียน key ชื่อชนกับ
                # callable (เช่น SL_BUFFER) แล้วทำให้ strategy เรียกแล้ว crash
                # ("'int' object is not callable")
                if callable(globals()[_k]):
                    print(f"⚠️ ข้าม optimized param '{_k}' — เป็น callable ทับไม่ได้")
                    continue
                globals()[_k] = _v
        print(f"✅ Loaded optimized parameters from {OPTIMIZED_PARAMS_FILE}")
    except Exception as _e:
        print(f"⚠️ Error loading optimized parameters: {_e}")
        try:
            from bot_log import log_error as _lerr
            _lerr("LOAD_OPTIMIZED_PARAMS_ERROR", f"{type(_e).__name__}: {_e}")
        except Exception:
            pass
S20_HTF_FVG_FILTER = True
S20_HTF_TFS = ['D1', 'H4']
