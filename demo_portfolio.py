"""
demo_portfolio.py — Live/demo runner for the "Champion" (P13) and "Max-Yield Blend" (P16)
research portfolios, fully independent from the S1-S20 live bot.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- ไม่แตะ scanner.py / active_strategies / bot_state.json (ไม่เขียนทับ ไม่ใช้ logic ของบอทหลัก)
- เรียก detect_s<N>() ตัวเดียวกับที่ backtest ใช้ ไม่มี logic ซ้ำ
- วางออเดอร์ด้วย mt5.order_send() ตรงๆ (ไม่ผ่าน mt5_utils.open_order_market เพราะจะโดน
  ML_SCORING_ENABLED / SCALE_OUT_ENABLED ที่ config.py เปิดอยู่โดย default — ทั้งสองตัวจะเปลี่ยน
  volume/filter สัญญาณแบบไม่ตรงกับสมมติฐานที่ backtest ใช้ (MIN_LOT คงที่, fixed SL/TP)
- SL/TP ฝากไว้กับ broker ตรงๆ (research พิสูจน์แล้วว่า fixed SL/TP ดีกว่า trailing/breakeven/
  partial-TP ทุกแบบที่ทดสอบ — ดู create_exit_optimization.md) ไม่ต้องมี exit-management เพิ่ม
- AF22/AF34/AF47 มี optional weighted sizing แยกต่างหาก ปิดไว้เป็น default และเปิด/ปรับ scale
  ผ่าน Telegram เท่านั้น เพื่อ forward-run แบบ lot เล็กก่อนหรือจำลอง weight backtest เมื่อพร้อม

⚠️ สำคัญ (เจอบั๊กจริงตอน deploy 2026-07-01): trailing.py มีฟังก์ชัน generic position-management
หลายสิบตัว (check_fill_trend_recheck, SL Guard Group, PD Zone fill check ฯลฯ) ที่สแกน
mt5.positions_get(symbol=SYMBOL) แบบ "ทุกโพซิชั่นในสัญลักษณ์" แล้ว skip เฉพาะ ticket ที่
position_sid.get(ticket) อยู่ใน skip-list ของฟังก์ชันนั้นๆ — ถ้าไม่ลงทะเบียน ticket ของเราไว้เลย
sid จะเป็น None ซึ่งไม่ตรง skip-list ใดๆ ทำให้ไม้ P13/P16 โดน logic ของบอทหลักไปจัดการ/ปิดก่อนถึง
SL/TP จริง (เจอจริง: ปิดขาดทุน -$0.01 ถึง -$0.49 ภายในไม่กี่สิบนาที ทั้งที่ SL ตั้งไกลกว่านั้นมาก)
แก้โดยลงทะเบียน position_sid[ticket] = 21 ทันทีหลังวางออเดอร์สำเร็จ — sid=21 เป็นค่าที่ถูก
"จอง" ไว้แล้วในทุก skip-list หลักของ trailing.py (SL_GUARD_SKIP_SIDS, SL_GUARD_GROUP_SKIP_SIDS,
PDFIBOPLUS_SKIP_SIDS, PENDING_LIMIT_GUARD_SKIP_SIDS, NEWS_FILTER_SKIP_SIDS,
OPPOSITE_ORDER_SKIP_SIDS, และ inline skip-tuple ของ check_fill_trend_recheck) — ตรงกับ
strategy21.py เดิมที่ import ไว้เฉยๆแต่ active_strategies ไม่มี key 21 (ไม่เคยถูกเรียกจริง) จึงใช้
sid นี้ tag ไม้ standalone ได้อย่างปลอดภัย ไม่ชนกับ strategy ไหน — position_sid ถูก
save/restore ผ่าน bot_state.json อยู่แล้ว (ของเดิมในระบบ) จึงรอดข้าม restart อัตโนมัติ
"""

import json
import os
import threading
import time
from datetime import datetime, timezone, timedelta

import mt5_worker as mt5
import config

from strategy31 import S31_DEFAULTS, detect_s31
from strategy34 import S34_DEFAULTS, detect_s34
from strategy36 import S36_DEFAULTS, detect_s36
from strategy37 import S37_DEFAULTS, detect_s37
from strategy38 import S38_DEFAULTS, detect_s38
from strategy39 import S39_DEFAULTS, detect_s39
from strategy40 import S40_DEFAULTS, detect_s40
from strategy41 import S41_DEFAULTS, detect_s41
from strategy42 import S42_DEFAULTS, detect_s42
from strategy44 import S44_DEFAULTS, detect_s44
from strategy45 import S45_DEFAULTS, detect_s45
from strategy46 import S46_DEFAULTS, detect_s46
from strategy47 import S47_DEFAULTS, detect_s47
from strategy49 import S49_DEFAULTS, detect_s49
from strategy51 import S51_DEFAULTS, detect_s51
from strategy56 import S56_DEFAULTS, detect_s56
from strategy_af import (
    AF_LADDER_LEGS,
    AF_PORTFOLIO_LEGS,
    AF_STRATEGIES,
    af_raw_cooldown_active,
    apply_af_filters,
)
from strategy_lts import LTS_PORTFOLIO_LEGS, LTS_STRATEGIES, detect_lts

from bot_log import log_event, log_error

STATE_FILE = os.path.join(
    getattr(config, "PROFILE_DIR", os.path.dirname(__file__))
    if getattr(config, "PROFILE_ACTIVE", False)
    else os.path.dirname(__file__),
    "demo_portfolio_state.json",
)
MAGIC_BASE = 990000  # แยกจาก magic=234001 ของ S1-S20 โดยสิ้นเชิง — P13=990013, P16=990016
AF_MAGIC_BASE = 991000  # AF22=991022, AF34=991034, AF47=991047
LTS_MAGIC_BASE = 992000  # LTS44=992044, LTS890=992890, LTS999=992999
MIN_LOT = 0.01
BKK_TZ = timezone(timedelta(hours=7))
_STATE_SAVE_LOCK = threading.Lock()

_TF_MAP = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15, 
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1
}
_TF_SECS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}


def _demo_symbol():
    return config.resolve_mt5_symbol(
        mt5,
        getattr(config, "DEMO_PORTFOLIO_SYMBOL", "XAUUSD"),
        set_runtime=False,
    )


def _demo_market_open(symbol):
    info = mt5.symbol_info(symbol)
    if info is None or getattr(info, "trade_mode", 0) == 0:
        return False, "trade disabled"
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return False, "no tick"
    bid = float(getattr(tick, "bid", 0.0) or 0.0)
    ask = float(getattr(tick, "ask", 0.0) or 0.0)
    if bid <= 0 and ask <= 0:
        return False, "no bid/ask"
    tick_ts = int(getattr(tick, "time", 0) or 0)
    if tick_ts <= 0:
        return False, "no tick time"
    now_ts = int(datetime.now().timestamp())
    if (now_ts - tick_ts) > 180:
        return False, "stale tick"
    return True, "open"


# ── tuned cfg เดียวกับที่ backtest ใช้เป๊ะๆ (จาก scratch/blend_17way.py) ──────────
_CFG_A = dict(S31_DEFAULTS); _CFG_A.update(SL_ATR_MULT=1.2, TP_RR=1.0)
_CFG_B = dict(S34_DEFAULTS); _CFG_B.update(BREAKOUT_LOOKBACK=8, VOLUME_SURGE_MULT=2.0,
                                            MIN_BREAKOUT_ATR=0.15, SL_ATR_MULT=0.8, TP_RR=1.0)
_CFG_C = dict(S36_DEFAULTS); _CFG_C.update(MIN_GAP_ATR=0.25, MAX_GAP_AGE_BARS=15,
                                            RETRACE_ENTRY_PCT=0.5, SL_ATR_MULT=1.0, TP_RR=0.8)
_CFG_D = dict(S37_DEFAULTS); _CFG_D.update(PIVOT_WING=3, MAX_LEVEL_AGE_BARS=60, TOUCH_ATR_MULT=0.3,
                                            REJECT_ATR_MULT=0.15, SL_ATR_MULT=0.8, TP_RR=1.5)
_CFG_E = dict(S38_DEFAULTS); _CFG_E.update(SWING_LOOKBACK_BARS=25, MIN_SWING_ATR=3.0,
                                            MAX_RETRACE_AGE_BARS=20, SL_ATR_MULT=1.0, TP_RR=1.0)
_CFG_F = dict(S39_DEFAULTS); _CFG_F.update(BASE_BARS=3, BASE_ATR_MULT=1.5, IMPULSE_ATR_MULT=0.8,
                                            MAX_ZONE_AGE_BARS=30, SL_ATR_MULT=0.8, TP_RR=1.5)
_CFG_G = dict(S40_DEFAULTS); _CFG_G.update(ZIGZAG_MIN_ATR=1.5, ZIGZAG_LOOKBACK_BARS=200,
                                            MAX_WAVE4_AGE_BARS=25, ENTRY_BREAK_ATR_MULT=0.1,
                                            SL_ATR_MULT=1.0, TP_RR=1.5)
_CFG_H = dict(S41_DEFAULTS); _CFG_H.update(PIVOT_WING=2, MIN_PRICE_DIFF_ATR=0.3, MIN_RSI_DIFF=3.0,
                                            MAX_CONFIRM_AGE_BARS=8, SL_ATR_MULT=0.8, TP_RR=1.0,
                                            CONFIRMATION_TYPE="htf_trend")
_CFG_I = dict(S42_DEFAULTS); _CFG_I.update(RANGE_BARS=9, SWEEP_ATR_MULT=0.5, MIN_RANGE_ATR=1.0,
                                            SL_ATR_MULT=1.0, TP_RR=1.0, CONFIRMATION_TYPE="htf_trend")
_CFG_K = dict(S44_DEFAULTS); _CFG_K.update(LOOKBACK_BARS=80, BUCKET_ATR_MULT=0.2, TOUCH_ATR_MULT=0.5,
                                            REJECT_ATR_MULT=0.15, SL_ATR_MULT=1.0, TP_RR=1.5)
_CFG_L = dict(S45_DEFAULTS); _CFG_L.update(IMPULSE_ATR_MULT=1.5, MAX_OB_AGE_BARS=40,
                                            MAX_VIOLATION_WICK_ATR=0.1, SL_ATR_MULT=1.0, TP_RR=1.5)
_CFG_M = dict(S46_DEFAULTS); _CFG_M.update(OR_SESSION_START="14:00", OR_MINUTES=30,
                                            MAX_BREAKOUT_AGE_MIN=90, MIN_BREAK_ATR=0.1,
                                            SL_ATR_MULT=0.8, TP_RR=1.5)
_CFG_N = dict(S47_DEFAULTS); _CFG_N.update(ST_ATR_PERIOD=20, ST_ATR_MULT=2.0, SL_ATR_MULT=1.5,
                                            TP_RR=2.0, SESSION_FILTER=False, CONFIRMATION_TYPE="htf_trend")
_CFG_P = dict(S49_DEFAULTS); _CFG_P.update(STD_MULT=1.0, TOUCH_ATR_MULT=0.2, REJECT_ATR_MULT=0.1,
                                            SL_ATR_MULT=1.0, TP_RR=1.0)
_CFG_Q = dict(S51_DEFAULTS); _CFG_Q.update(TOUCH_ATR_MULT=0.5, REJECT_ATR_MULT=0.1, SL_ATR_MULT=0.8,
                                            TP_RR=1.5, SESSION_FILTER=False)
_CFG_R = dict(S56_DEFAULTS); _CFG_R.update(TOUCH_ATR_MULT=0.8, REJECT_ATR_MULT=0.15, SL_ATR_MULT=1.0,
                                            TP_RR=1.5, CONFIRMATION_TYPE="none", SESSION_FILTER=False)

# leg registry: (label, detect_fn, cfg, needs_htf, extra_kind)
# extra_kind: None | "bar_dt_list" (S46/S49/S51) | "prev_week_hl" (S56)
_LEG_DEFS = {
    "A": ("S31 Engulfing",         detect_s31, _CFG_A, True,  None),
    "B": ("S34 VolBreak",          detect_s34, _CFG_B, True,  None),
    "C": ("S36 FVG",               detect_s36, _CFG_C, True,  None),
    "D": ("S37 S/R Pivot",         detect_s37, _CFG_D, True,  None),
    "E": ("S38 Fibonacci OTE",     detect_s38, _CFG_E, True,  None),
    "F": ("S39 Demand/Supply",     detect_s39, _CFG_F, True,  None),
    "G": ("S40 Elliott",           detect_s40, _CFG_G, True,  None),
    "H": ("S41 RSI Div",           detect_s41, _CFG_H, True,  None),
    "I": ("S42 CRT",               detect_s42, _CFG_I, True,  None),
    "K": ("S44 VolProfile",        detect_s44, _CFG_K, True,  None),
    "L": ("S45 OrderBlock",        detect_s45, _CFG_L, True,  None),
    "M": ("S46 ORB",               detect_s46, _CFG_M, True,  "bar_dt_list"),
    "N": ("S47 SuperTrend",        detect_s47, _CFG_N, True,  None),
    "P": ("S49 VWAP",              detect_s49, _CFG_P, True,  "bar_dt_list"),
    "Q": ("S51 PDH/PDL",           detect_s51, _CFG_Q, True,  "bar_dt_list"),
    "R": ("S56 PrevWeekHL",        detect_s56, _CFG_R, False, "prev_week_hl"),
}

AF_DEFS = {**AF_LADDER_LEGS, **LTS_STRATEGIES}

P13_KEYS = list("BCDFGHIKMNPQR")  # Champion — ถอด A(S31)/E(S38)/L(S45) ที่เป็น sharpe-drag
P16_KEYS = list("ABCDEFGHIKLMNPQR")  # Max-Yield Blend — ครบทุก leg

PORTFOLIOS = {"P13": P13_KEYS, "P16": P16_KEYS, **AF_PORTFOLIO_LEGS, **LTS_PORTFOLIO_LEGS}
PORTFOLIO_DISPLAY_NAME = {
    "P13": "🏆 Champion (P13)",
    "P16": "💰 Max-Yield Blend (P16)",
    "AF22": "🎯 AF22 $1000",
    "AF34": "🎯 AF34 $1500",
    "AF47": "🎯 AF47 $2000",
    "LTS44": "🛡️ LTS44 $500",
    "LTS890": "🌌 LTS890 $10K",
    "LTS999": "🚀 LTS999 Ultra Safe",
}
PORTFOLIO_ORDER = ("P13", "P16", "AF22", "AF34", "AF47", "LTS44", "LTS890", "LTS999")


def _now_bkk():
    return datetime.now(BKK_TZ)


def _portfolio_magic(portfolio_name: str) -> int:
    if portfolio_name.startswith("LTS"):
        return LTS_MAGIC_BASE + int(portfolio_name.replace("LTS", ""))
    if portfolio_name.startswith("AF"):
        return AF_MAGIC_BASE + int(portfolio_name[2:])
    return MAGIC_BASE + int(portfolio_name[1:])


def _leg_label(key: str) -> str:
    if key in _LEG_DEFS:
        return _LEG_DEFS[key][0]
    if key in AF_DEFS:
        return AF_DEFS[key]["label"]
    return key


def _fetch_bars(tf_str, count):
    rates = mt5.copy_rates_from_pos(_demo_symbol(), _TF_MAP[tf_str], 0, count)
    if rates is None or len(rates) == 0:
        return None
    return rates


def _calc_ema_adx_htf(htf_bars, cfg):
    """คัดลอก logic เดียวกับ sim_s30_backtest.build_htf_series/htf_lookup แบบย่อสำหรับ live —
    ใช้เฉพาะแท่ง HTF ที่ปิดสมบูรณ์แล้ว (close_time <= now) เท่านั้น ไม่มี lookahead"""
    import sim_s30_backtest as s30sim
    series = s30sim.build_htf_series(htf_bars, cfg)
    return series


def _htf_ctx_now(htf_series, entry_ts):
    import sim_s30_backtest as s30sim
    return s30sim.htf_lookup(htf_series, entry_ts)


def _build_bar_dt_list(bars):
    return [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]


def _prev_week_hl_now(entry_ts):
    """high/low ของสัปดาห์ก่อนหน้า (W1 bar ก่อนหน้าสัปดาห์ปัจจุบัน) — เหมือน sim_s56_backtest"""
    w1 = mt5.copy_rates_from_pos(_demo_symbol(), mt5.TIMEFRAME_W1, 0, 12)
    if w1 is None or len(w1) == 0:
        return None
    starts = sorted(int(b["time"]) for b in w1)
    hl = {int(b["time"]): (float(b["high"]), float(b["low"])) for b in w1}
    import bisect
    idx = bisect.bisect_right(starts, entry_ts) - 1
    if idx <= 0:
        return None
    return hl[starts[idx - 1]]


def _load_state():
    if not os.path.exists(STATE_FILE):
        return {"active": {"P13": False, "P16": False}, "last_signal_ts": {}, "last_raw_signal_ts": {}, "trades": []}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            state.setdefault("active", {"P13": False, "P16": False})
            state.setdefault("last_signal_ts", {})
            state.setdefault("last_raw_signal_ts", {})
            state.setdefault("trades", [])
            return state
    except Exception:
        return {"active": {"P13": False, "P16": False}, "last_signal_ts": {}, "last_raw_signal_ts": {}, "trades": []}


def _save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    last_error = None
    with _STATE_SAVE_LOCK:
        for attempt in range(5):
            tmp = f"{STATE_FILE}.{os.getpid()}.{threading.get_ident()}.{attempt}.tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, STATE_FILE)
                return True
            except PermissionError as e:
                last_error = e
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
                time.sleep(0.15 * (attempt + 1))
            except Exception as e:
                last_error = e
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
                break
    try:
        log_error("DEMO_PORTFOLIO_STATE", f"save failed: {type(last_error).__name__}: {last_error}")
    except Exception:
        pass
    return False


def _demo_comment(leg_id, entry_tf):
    return f"{entry_tf}-{leg_id}"


def _strategy_doc(af_def):
    return af_def.get("doc") or af_def.get("formula") or af_def.get("label") or af_def.get("key", "")


def _count_open_positions(magic, leg_id, entry_tf=None):
    """นับไม้ที่เปิดค้างอยู่ของ leg นี้โดยเฉพาะ (แยกด้วย comment prefix ของ leg_id) —
    ใช้กัน leg เดียวยิงไม้ใหม่ซ้อนกันไม่จำกัดตอนเทรนด์แรง (เจอจริง 2026-07-02: leg D/K
    ค้าง 5-6 ไม้พร้อมกัน จน margin บัญชีเล็กหมด ออเดอร์อื่นโดน 10019 No money)"""
    positions = mt5.positions_get(symbol=_demo_symbol())
    if not positions:
        return 0
    prefixes = [
        leg_id,
        f"DEMO-{leg_id}",  # legacy format before TF was moved after DEMO
    ]
    if entry_tf:
        prefixes.append(_demo_comment(leg_id, entry_tf))
        prefixes.append(f"DEMO-{entry_tf}-{leg_id}")  # legacy format with TF after DEMO
    return sum(1 for p in positions if p.magic == magic and any(p.comment.startswith(prefix) for prefix in prefixes))


def _round_volume(volume, info):
    vol_min = float(getattr(info, "volume_min", 0.01) or 0.01)
    vol_max = float(getattr(info, "volume_max", 100.0) or 100.0)
    vol_step = float(getattr(info, "volume_step", 0.01) or 0.01)
    cap_cfg = float(getattr(config, "DEMO_PORTFOLIO_AF_MAX_LOT", 0.0) or 0.0)
    cap = min(vol_max, cap_cfg) if cap_cfg > 0 else vol_max
    volume = max(vol_min, min(float(volume), cap))
    steps = round((volume - vol_min) / vol_step)
    return round(vol_min + steps * vol_step, 2)


def _af_order_volume(af_def, portfolio_name, tf=None, signal=None):
    weight_enabled = getattr(config, "DEMO_PORTFOLIO_WEIGHT_ENABLED", {}).get(portfolio_name, False)
    weight_scale = getattr(config, "DEMO_PORTFOLIO_WEIGHT_SCALE", {}).get(portfolio_name, 1.0)
    
    from mt5_utils import get_dynamic_volume
    base_raw = MIN_LOT
    if portfolio_name.startswith("LTS") and tf and signal:
        base_raw = get_dynamic_volume(tf, signal, base_vol=MIN_LOT, portfolio=portfolio_name)
        
    if not weight_enabled:
        info = mt5.symbol_info(_demo_symbol())
        volume = _round_volume(base_raw, info) if info else round(base_raw, 2)
        return volume, {
            "weighted": False,
            "weight": float(af_def.get("weight", 1.0)),
            "scale": float(weight_scale),
            "raw_volume": base_raw,
        }
    weight = float(af_def.get("weight", 1.0))
    scale = float(weight_scale)
    raw_volume = base_raw * weight * scale
    info = mt5.symbol_info(_demo_symbol())
    volume = _round_volume(raw_volume, info) if info else round(raw_volume, 2)
    return volume, {"weighted": True, "weight": weight, "scale": scale, "raw_volume": raw_volume}


def _place_market_order(signal, sl, tp, comment, magic, volume=MIN_LOT, original_entry=0.0):
    """วางออเดอร์ตรงๆ ผ่าน mt5.order_send() — ไม่ผ่าน mt5_utils.open_order_market() เพื่อเลี่ยง
    ML_SCORING_ENABLED / SCALE_OUT_ENABLED ที่เป็น global toggle ของบอทเดิม (ดู docstring บนไฟล์)"""
    symbol = _demo_symbol()
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return {"success": False, "error": "ดึงราคาไม่ได้"}
    price = tick.ask if signal == "BUY" else tick.bid
    
    # 1. Shift SL/TP by the difference between execution price and original signal entry
    if original_entry > 0:
        delta = price - original_entry
        sl += delta
        if tp > 0:
            tp += delta
            
    # 2. Clamp SL/TP to respect broker's SYMTBOL_TRADE_STOPS_LEVEL
    info = mt5.symbol_info(symbol)
    if info:
        min_stops = float(getattr(info, "trade_stops_level", 0.0) or 0.0) * float(getattr(info, "point", 0.0) or 0.0)
        if min_stops > 0:
            min_stops += float(getattr(info, "point", 0.0) or 0.0) * 2.0  # +2 points buffer
        if signal == "BUY":
            if sl > price - min_stops: sl = price - min_stops
            if tp > 0 and tp < price + min_stops: tp = price + min_stops
        else:
            if sl > 0 and sl < price + min_stops: sl = price + min_stops
            if tp > 0 and tp > price - min_stops: tp = price - min_stops

    order_type = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
    try:
        margin = mt5.order_calc_margin(order_type, symbol, float(volume), price)
        account = mt5.account_info()
        free_margin = float(getattr(account, "margin_free", 0.0) or 0.0) if account else 0.0
        if margin is not None and free_margin > 0 and float(margin) > free_margin:
            return {"success": False, "error": f"margin not enough: need {float(margin):.2f}, free {free_margin:.2f}", "sl": sl, "tp": tp}
    except Exception:
        pass
    result = mt5.order_send({
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": magic,
        "comment": comment[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    })
    if result is None:
        return {"success": False, "error": f"order_send returned None — {mt5.last_error()}", "sl": sl, "tp": tp}
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        return {"success": True, "ticket": result.order, "price": price, "sl": sl, "tp": tp}
    return {"success": False, "error": f"{result.retcode} — {result.comment}", "sl": sl, "tp": tp}


async def _demo_scan_af(app, portfolio_name: str):
    af_def = AF_DEFS[portfolio_name]
    state = _load_state()
    magic = _portfolio_magic(portfolio_name)
    cfg = af_def["cfg"]
    entry_tf = cfg["ENTRY_TF"]
    bars = _fetch_bars(entry_tf, 500)
    if bars is None:
        log_error("DEMO_PORTFOLIO", f"{portfolio_name}: fetch {entry_tf} bars failed")
        return

    entry_ts = int(bars[-1]["time"])
    k = af_def['key']
    leg_id = k if k.startswith(portfolio_name) else f"{portfolio_name}-{k}"
    if state["last_signal_ts"].get(leg_id) == entry_ts:
        return
    if af_raw_cooldown_active(state["last_raw_signal_ts"].get(leg_id), entry_ts, af_def, bars=bars):
        return

    now = _now_bkk()
    fill_dt = config.mt5_ts_to_bkk(entry_ts)
    try:
        res = af_def["detect_fn"](bars, tf=entry_tf, dt_bkk=fill_dt, cfg=cfg)
    except Exception as e:
        log_error("DEMO_PORTFOLIO", f"{leg_id} detect error: {type(e).__name__}: {e}")
        return

    if res.get("signal") in ("BUY", "SELL"):
        state["last_raw_signal_ts"][leg_id] = entry_ts

    filtered, reason = apply_af_filters(res, af_def, entry_ts)
    if filtered is None:
        if reason != "no_signal":
            _save_state(state)
            log_event("DEMO_PORTFOLIO_SKIP", f"{leg_id} skipped — {reason}")
        return

    state["last_signal_ts"][leg_id] = entry_ts
    open_count = _count_open_positions(magic, leg_id, entry_tf)
    if open_count >= config.DEMO_PORTFOLIO_MAX_POS_PER_LEG:
        log_event("DEMO_PORTFOLIO_SKIP",
                  f"{leg_id} {filtered['signal']} skipped — {open_count} positions already open "
                  f"(cap={config.DEMO_PORTFOLIO_MAX_POS_PER_LEG})")
        return

    sig = filtered["signal"]
    sl, tp = float(filtered["sl"]), float(filtered["tp"])
    original_entry = float(filtered.get("entry", 0.0))
    volume, volume_meta = _af_order_volume(af_def, portfolio_name, entry_tf, sig)
    comment = _demo_comment(leg_id, entry_tf)
    result = _place_market_order(sig, sl, tp, comment, magic, volume=volume, original_entry=original_entry)
    
    sl = result.get("sl", sl)
    tp = result.get("tp", tp)

    if result.get("success") and result.get("ticket"):
        try:
            from trailing import position_sid
            position_sid[result["ticket"]] = 21
        except Exception as e:
            log_error("DEMO_PORTFOLIO", f"register position_sid failed: {type(e).__name__}: {e}")

    trade_log = {
        "ts": now.isoformat(),
        "entry_bar_ts": entry_ts,
        "leg": leg_id,
        "label": af_def["label"],
        "signal": sig,
        "sl": sl,
        "tp": tp,
        "success": result.get("success"),
        "ticket": result.get("ticket"),
        "error": result.get("error"),
        "risk_distance": filtered["risk_distance"],
        "fill_hour": filtered["fill_hour"],
        "volume": volume,
        "weighted_sizing": volume_meta["weighted"],
        "weight": volume_meta["weight"],
        "weight_scale": volume_meta["scale"],
        "raw_volume": volume_meta["raw_volume"],
        "doc": _strategy_doc(af_def),
    }
    state["trades"].append(trade_log)
    state["trades"] = state["trades"][-500:]
    _save_state(state)

    log_event("DEMO_PORTFOLIO_SIGNAL",
              f"{leg_id} {sig} lot={volume:.2f} sl={sl} tp={tp} rd={filtered['risk_distance']:.2f} "
              f"weight={volume_meta['weight']:.3f} scale={volume_meta['scale']:.2f} "
              f"h={filtered['fill_hour']} success={result.get('success')} "
              f"ticket={result.get('ticket')} err={result.get('error')}")

    if app is not None and result.get("success"):
        try:
            msg = (f"📡 *{PORTFOLIO_DISPLAY_NAME[portfolio_name]}*\n"
                   f"Leg: `{af_def['label']}`\n"
                   f"{'🟢 BUY' if sig=='BUY' else '🔴 SELL'} @ market lot `{volume:.2f}`\n"
                   f"SL `{sl:.2f}` TP `{tp:.2f}`\n"
                   f"RD `{filtered['risk_distance']:.2f}` H`{filtered['fill_hour']}`\n"
                   f"Weight `x{volume_meta['weight']:.3f}` Scale `{volume_meta['scale']:.2f}`\n"
                   f"Ticket: `{result.get('ticket')}`")
            await app.bot.send_message(chat_id=config.MY_USER_ID, text=msg, parse_mode="Markdown")
        except Exception:
            pass
    elif app is not None and not result.get("success") and not result.get("skipped"):
        try:
            await app.bot.send_message(
                chat_id=config.MY_USER_ID,
                text=f"⚠️ Demo Portfolio {leg_id} order failed: {result.get('error')}",
            )
        except Exception:
            pass


async def _demo_scan_af_ladder(app, portfolio_name: str):
    state = _load_state()
    magic = _portfolio_magic(portfolio_name)
    now = _now_bkk()
    bars_cache = {}

    for key in PORTFOLIOS[portfolio_name]:
        af_def = AF_DEFS[key]
        cfg = af_def["cfg"]
        entry_tf = cfg["ENTRY_TF"]
        if entry_tf not in bars_cache:
            bars_cache[entry_tf] = _fetch_bars(entry_tf, 500)
        bars = bars_cache[entry_tf]
        if bars is None:
            log_error("DEMO_PORTFOLIO", f"{portfolio_name}: fetch {entry_tf} bars failed")
            continue

        entry_ts = int(bars[-1]["time"])
        k = af_def['key']
        leg_id = k if k.startswith(portfolio_name) else f"{portfolio_name}-{k}"
        if state["last_signal_ts"].get(leg_id) == entry_ts:
            continue
        if af_raw_cooldown_active(state["last_raw_signal_ts"].get(leg_id), entry_ts, af_def, bars=bars):
            continue

        fill_dt = config.mt5_ts_to_bkk(entry_ts)
        try:
            res = af_def["detect_fn"](bars, tf=entry_tf, dt_bkk=fill_dt, cfg=cfg)
        except Exception as e:
            log_error("DEMO_PORTFOLIO", f"{leg_id} detect error: {type(e).__name__}: {e}")
            continue

        if res.get("signal") in ("BUY", "SELL"):
            state["last_raw_signal_ts"][leg_id] = entry_ts

        filtered, reason = apply_af_filters(res, af_def, entry_ts)
        if filtered is None:
            if reason != "no_signal":
                _save_state(state)
                log_event("DEMO_PORTFOLIO_SKIP", f"{leg_id} skipped - {reason}")
            continue

        state["last_signal_ts"][leg_id] = entry_ts
        cap = int(getattr(config, "DEMO_PORTFOLIO_AF_MAX_POS_PER_LEG", 0) or 0)
        open_count = _count_open_positions(magic, leg_id, entry_tf)
        if cap > 0 and open_count >= cap:
            log_event(
                "DEMO_PORTFOLIO_SKIP",
                f"{leg_id} {filtered['signal']} skipped - {open_count} positions already open "
                f"(af_cap={cap})",
            )
            continue

        sig = filtered["signal"]
        sl, tp = float(filtered["sl"]), float(filtered["tp"])
        original_entry = float(filtered.get("entry", 0.0))
        volume, volume_meta = _af_order_volume(af_def, portfolio_name)
        comment = _demo_comment(leg_id, entry_tf)
        result = _place_market_order(sig, sl, tp, comment, magic, volume=volume, original_entry=original_entry)

        sl = result.get("sl", sl)
        tp = result.get("tp", tp)

        if result.get("success") and result.get("ticket"):
            try:
                from trailing import position_sid
                position_sid[result["ticket"]] = 21
            except Exception as e:
                log_error("DEMO_PORTFOLIO", f"register position_sid failed: {type(e).__name__}: {e}")

        state["trades"].append({
            "ts": now.isoformat(),
            "entry_bar_ts": entry_ts,
            "leg": leg_id,
            "label": af_def["label"],
            "signal": sig,
            "sl": sl,
            "tp": tp,
            "success": result.get("success"),
            "ticket": result.get("ticket"),
            "error": result.get("error"),
            "risk_distance": filtered["risk_distance"],
            "fill_hour": filtered["fill_hour"],
            "volume": volume,
            "weighted_sizing": volume_meta["weighted"],
            "weight": volume_meta["weight"],
            "weight_scale": volume_meta["scale"],
            "raw_volume": volume_meta["raw_volume"],
            "doc": _strategy_doc(af_def),
        })
        state["trades"] = state["trades"][-1000:]
        _save_state(state)

        log_event(
            "DEMO_PORTFOLIO_SIGNAL",
            f"{leg_id} {sig} lot={volume:.2f} sl={sl} tp={tp} rd={filtered['risk_distance']:.2f} "
            f"weight={volume_meta['weight']:.3f} scale={volume_meta['scale']:.2f} "
            f"h={filtered['fill_hour']} success={result.get('success')} "
            f"ticket={result.get('ticket')} err={result.get('error')}",
        )

        if app is not None and result.get("success"):
            try:
                msg = (
                    f"[AF SIGNAL] *{PORTFOLIO_DISPLAY_NAME[portfolio_name]}*\n"
                    f"Leg: `{af_def['label']}`\n"
                    f"{sig} @ market lot `{volume:.2f}`\n"
                    f"SL `{sl:.2f}` TP `{tp:.2f}`\n"
                    f"RD `{filtered['risk_distance']:.2f}` H`{filtered['fill_hour']}`\n"
                    f"Weight `x{volume_meta['weight']:.3f}` Scale `{volume_meta['scale']:.2f}`\n"
                    f"Ticket: `{result.get('ticket')}`"
                )
                await app.bot.send_message(chat_id=config.MY_USER_ID, text=msg, parse_mode="Markdown")
            except Exception:
                pass
        elif app is not None and not result.get("success") and not result.get("skipped"):
            try:
                await app.bot.send_message(
                    chat_id=config.MY_USER_ID,
                    text=f"Demo Portfolio {leg_id} order failed: {result.get('error')}",
                )
            except Exception:
                pass


async def demo_scan(app, portfolio_name: str):
    """สแกน 1 รอบสำหรับ portfolio ที่ระบุ (P13 หรือ P16) — เรียก detect_s<N>() ของทุก leg
    ด้วยข้อมูล live ล่าสุด ถ้ามี signal ใหม่ (และไม่ติด cooldown) วางออเดอร์ตลาดทันที"""
    if not config.DEMO_PORTFOLIO_ACTIVE.get(portfolio_name, False):
        return
    if portfolio_name in AF_PORTFOLIO_LEGS or portfolio_name.startswith("LTS"):
        await _demo_scan_af_ladder(app, portfolio_name)
        return

    state = _load_state()
    keys = PORTFOLIOS[portfolio_name]
    magic = _portfolio_magic(portfolio_name)  # P13->990013, P16->990016

    entry_bars = _fetch_bars("M5", 400)
    if entry_bars is None:
        log_error("DEMO_PORTFOLIO", f"{portfolio_name}: fetch M5 bars failed")
        return
    htf_bars = _fetch_bars("M15", 200)
    now = _now_bkk()
    entry_ts = int(entry_bars[-1]["time"])

    for key in keys:
        label, detect_fn, cfg, needs_htf, extra_kind = _LEG_DEFS[key]
        leg_id = f"{portfolio_name}-{key}"

        # cooldown เดียวกับ MIN_GAP_BARS=1 ของ backtest — ห้ามยิงซ้ำในแท่งเดียวกัน
        last_ts = state["last_signal_ts"].get(leg_id)
        if last_ts == entry_ts:
            continue

        htf_ctx = None
        if needs_htf and cfg.get("CONFIRMATION_TYPE", "htf_trend") != "none" and htf_bars is not None:
            htf_series = _calc_ema_adx_htf(htf_bars, cfg)
            htf_ctx = _htf_ctx_now(htf_series, entry_ts)

        kwargs = {"tf": "M5", "dt_bkk": now, "cfg": cfg, "htf_ctx": htf_ctx}
        if extra_kind == "bar_dt_list":
            kwargs["bar_dt_list"] = _build_bar_dt_list(entry_bars[:-1])
        elif extra_kind == "prev_week_hl":
            kwargs["prev_week_hl"] = _prev_week_hl_now(entry_ts)

        try:
            res = detect_fn(entry_bars, **kwargs)
        except Exception as e:
            log_error("DEMO_PORTFOLIO", f"{leg_id} detect error: {type(e).__name__}: {e}")
            continue

        sig = res.get("signal")
        if sig not in ("BUY", "SELL"):
            continue

        state["last_signal_ts"][leg_id] = entry_ts

        open_count = _count_open_positions(magic, leg_id, "M5")
        if open_count >= config.DEMO_PORTFOLIO_MAX_POS_PER_LEG:
            log_event("DEMO_PORTFOLIO_SKIP",
                       f"{leg_id} {sig} skipped — {open_count} positions already open "
                       f"(cap={config.DEMO_PORTFOLIO_MAX_POS_PER_LEG})")
            continue

        sl, tp = float(res["sl"]), float(res["tp"])
        original_entry = float(res.get("entry", 0.0))
        comment = _demo_comment(leg_id, "M5")
        result = _place_market_order(sig, sl, tp, comment, magic, original_entry=original_entry)

        sl = result.get("sl", sl)
        tp = result.get("tp", tp)

        if result.get("success") and result.get("ticket"):
            # ⚠️ ต้องลงทะเบียนด้วย sid=21 ทันที ไม่งั้น trailing.py จะเห็น sid=None แล้วไม่ skip
            # (บั๊กจริงที่เจอ 2026-07-01 — ดู docstring บนไฟล์นี้) sid=21 = ค่าจองไว้แล้วในทุก
            # skip-list หลักของ trailing.py สำหรับ standalone strategy โดยเฉพาะ
            try:
                from trailing import position_sid
                position_sid[result["ticket"]] = 21
            except Exception as e:
                log_error("DEMO_PORTFOLIO", f"register position_sid failed: {type(e).__name__}: {e}")

        trade_log = {
            "ts": now.isoformat(), "entry_bar_ts": entry_ts, "leg": leg_id, "label": label,
            "signal": sig, "sl": sl, "tp": tp, "success": result.get("success"),
            "ticket": result.get("ticket"), "error": result.get("error"),
        }
        # entry_bar_ts = MT5 server timestamp ดิบของแท่งที่ยิง signal (ไม่ใช่ BKK wall-clock)
        # เก็บไว้ให้ tool ตรวจสอบย้อนหลัง (เช่น verify_signal_consistency.py) fetch ราคาย้อนหลัง
        # ตรงเป๊ะได้โดยไม่ต้องคำนวณ timezone กลับไปกลับมา (เคยพลาดตรงนี้มาก่อน)
        state["trades"].append(trade_log)
        state["trades"] = state["trades"][-500:]  # กัน state file โตไม่จำกัด
        _save_state(state)

        log_event("DEMO_PORTFOLIO_SIGNAL",
                   f"{leg_id} {sig} sl={sl} tp={tp} success={result.get('success')} "
                   f"ticket={result.get('ticket')} err={result.get('error')}")

        if app is not None and result.get("success"):
            try:
                msg = (f"📡 *{PORTFOLIO_DISPLAY_NAME[portfolio_name]}*\n"
                       f"Leg: `{label}` ({key})\n"
                       f"{'🟢 BUY' if sig=='BUY' else '🔴 SELL'} @ market\n"
                       f"SL `{sl:.2f}` TP `{tp:.2f}`\n"
                       f"Ticket: `{result.get('ticket')}`")
                await app.bot.send_message(chat_id=config.MY_USER_ID, text=msg, parse_mode="Markdown")
            except Exception:
                pass
        elif app is not None and not result.get("success") and not result.get("skipped"):
            try:
                await app.bot.send_message(
                    chat_id=config.MY_USER_ID,
                    text=f"⚠️ Demo Portfolio {leg_id} order failed: {result.get('error')}",
                )
            except Exception:
                pass


async def demo_scan_job(app):
    """เรียกจาก scheduler ใน main.py ทุก DEMO_PORTFOLIO_SCAN_INTERVAL นาที — no-op ถ้าไม่มี
    portfolio ไหน active เลย"""
    active_names = [name for name in PORTFOLIO_ORDER if config.DEMO_PORTFOLIO_ACTIVE.get(name, False)]
    if not active_names:
        return
    symbol = _demo_symbol()
    market_open, reason = _demo_market_open(symbol)
    if not market_open:
        log_event("DEMO_PORTFOLIO_SKIP", f"{symbol} market closed - {reason}", active=",".join(active_names))
        return
    log_event("DEMO_PORTFOLIO_SCAN", f"{symbol} open active={','.join(active_names)}")
    for name in active_names:
        try:
            await demo_scan(app, name)
        except Exception as e:
            log_error("DEMO_PORTFOLIO", f"{name} scan error: {type(e).__name__}: {e}")
    log_event("DEMO_PORTFOLIO_SCAN", f"{symbol} done active={','.join(active_names)}")


def _fetch_leg_pnl(portfolio_name: str):
    """
    ดึงกำไร/ขาดทุนแยกตาม leg ทั้ง 2 แบบ:
    - "total"/"n_closed" = realized (ไม้ที่ปิดจบแล้วจริงๆ ผ่าน SL/TP ที่ broker) — ย้อนดู deal
      history ของ MT5 เพราะ Python ไม่ได้คอยเช็คเอง
    - "floating" = unrealized (ไม้ที่ยังเปิดอยู่ตอนนี้ ราคายังไม่แตะ SL/TP) — ดึงจาก
      positions_get() ตรงๆ (ลอยได้ทั้งบวกและลบ ยังไม่ใช่กำไรจริงจนกว่าจะปิด)
    match กลับด้วย ticket ที่บันทึกไว้ตอนวางออเดอร์ (state["trades"])

    คืน dict: {leg_id: {"total": float, "n_closed": int, "floating": float, "first_ts": str}}
    """
    state = _load_state()
    tickets = {t["ticket"]: (t["leg"], t["ts"]) for t in state["trades"]
               if t.get("success") and t.get("ticket") and t["leg"].startswith(f"{portfolio_name}-")}
    result = {}
    for leg_id, ts in tickets.values():
        d = result.setdefault(leg_id, {"total": 0.0, "n_closed": 0, "floating": 0.0, "first_ts": ts})
        if ts < d["first_ts"]:
            d["first_ts"] = ts

    if not tickets:
        return result

    magic = _portfolio_magic(portfolio_name)

    # ── floating (ไม้ที่ยังเปิดอยู่ตอนนี้) ──────────────────────────────────
    open_positions = mt5.positions_get(symbol=_demo_symbol())
    if open_positions:
        for p in open_positions:
            if p.magic != magic:
                continue
            leg_info = tickets.get(p.ticket)
            if leg_info is None:
                continue
            d = result.setdefault(leg_info[0], {"total": 0.0, "n_closed": 0, "floating": 0.0,
                                                 "first_ts": leg_info[1]})
            d["floating"] += float(p.profit) + float(p.swap)

    # ── realized (ไม้ที่ปิดจบแล้ว) ───────────────────────────────────────────
    from datetime import timedelta as _td
    date_from = datetime.now(timezone.utc) - _td(days=200)
    date_to = datetime.now(timezone.utc) + _td(days=1)
    deals = mt5.history_deals_get(date_from, date_to)
    if not deals:
        return result

    for deal in deals:
        if deal.magic != magic:
            continue
        if deal.entry != mt5.DEAL_ENTRY_OUT:  # เอาเฉพาะ deal ที่ "ปิด" position (มีกำไร/ขาดทุนจริง)
            continue
        leg_info = tickets.get(deal.position_id)
        if leg_info is None:
            continue
        leg_id = leg_info[0]
        d = result.setdefault(leg_id, {"total": 0.0, "n_closed": 0, "floating": 0.0,
                                        "first_ts": leg_info[1]})
        d["total"] += float(deal.profit) + float(deal.swap) + float(deal.commission)
        d["n_closed"] += 1
    return result


def get_symbol_exposure_text(symbol_root: str) -> str:
    symbol_root = str(symbol_root or "").upper()
    symbol = config.resolve_mt5_symbol(mt5, symbol_root, set_runtime=False)
    lines = [
        f"*{symbol_root} Detail*",
        f"Symbol: {symbol}",
    ]
    if symbol_root != "XAUUSD":
        lines.append("P13/P16/AF ถูกตั้งให้เทรดเฉพาะ XAUUSD เท่านั้น")

    open_positions = mt5.positions_get(symbol=symbol)
    pf_positions = []
    if open_positions:
        allowed_magic = {_portfolio_magic(name) for name in PORTFOLIO_ORDER}
        pf_positions = [p for p in open_positions if p.magic in allowed_magic]

    if not pf_positions:
        lines.append("ไม่มี position ของ Demo Portfolio บน symbol นี้")
        return "\n".join(lines)

    lines.append(f"โพซิชั่นเปิดอยู่: {len(pf_positions)} ไม้")
    for p in pf_positions[:20]:
        portfolio = next((name for name in PORTFOLIO_ORDER if _portfolio_magic(name) == p.magic), str(p.magic))
        lines.append(
            f"  `{portfolio}` #{p.ticket} {'BUY' if p.type == 0 else 'SELL'} "
            f"{p.volume} comment:`{p.comment}` PnL:`{p.profit:.2f}`"
        )
    return "\n".join(lines)


def get_status_text(portfolio_name: str) -> str:
    """สรุปสถานะสำหรับ Telegram status view — รวมกำไรเฉลี่ยต่อวัน/เดือน/กำไรรวม แยกราย leg"""
    state = _load_state()
    is_active = config.DEMO_PORTFOLIO_ACTIVE.get(portfolio_name, False)
    keys = PORTFOLIOS[portfolio_name]
    magic = _portfolio_magic(portfolio_name)

    today = _now_bkk().date().isoformat()
    trades_today = [t for t in state["trades"]
                    if t["leg"].startswith(f"{portfolio_name}-") and t["ts"].startswith(today)]
    n_success = sum(1 for t in trades_today if t.get("success"))

    lines = [
        f"{PORTFOLIO_DISPLAY_NAME[portfolio_name]}",
        f"สถานะ: {'🟢 ทำงานอยู่' if is_active else '⚪ หยุดอยู่'}",
        f"Symbol: {_demo_symbol()}",
        f"จำนวน leg: {len(keys)}",
        f"Magic: {magic}",
        f"ออเดอร์วันนี้: {n_success} ไม้",
    ]
    if portfolio_name in AF_PORTFOLIO_LEGS or portfolio_name.startswith("LTS"):
        weights = [float(AF_DEFS[k].get("weight", 1.0)) for k in keys]
        scale = float(getattr(config, "DEMO_PORTFOLIO_WEIGHT_SCALE", {}).get(portfolio_name, 1.0))
        sizing_on = getattr(config, "DEMO_PORTFOLIO_WEIGHT_ENABLED", {}).get(portfolio_name, False)
        lot_min = MIN_LOT * (min(weights) * scale if sizing_on and weights else 1.0)
        lot_max = MIN_LOT * (max(weights) * scale if sizing_on and weights else 1.0)
        lines.extend([
            f"AF ladder mode: full {portfolio_name} = AF1..AF{len(keys)}",
            f"AF weighted sizing: {'ON' if sizing_on else 'OFF'} | scale {scale:.2f}",
            f"Leg weight range: x{min(weights):.3f}-x{max(weights):.3f}",
            f"Lot preview per leg: ~{lot_min:.2f}-{lot_max:.2f}",
            f"AF max positions/leg: {getattr(config, 'DEMO_PORTFOLIO_AF_MAX_POS_PER_LEG', 0) or 'no cap'}",
        ])

    open_positions = mt5.positions_get(symbol=_demo_symbol())
    if open_positions:
        pf_positions = [p for p in open_positions if p.magic == magic]
        if pf_positions:
            lines.append(f"\nโพซิชั่นเปิดอยู่: {len(pf_positions)} ไม้")
            for p in pf_positions[:10]:
                lines.append(f"  #{p.ticket} {'BUY' if p.type==0 else 'SELL'} "
                             f"{p.volume} SL:{p.sl:.2f} TP:{p.tp:.2f} PnL:{p.profit:.2f}")

    # ── กำไร/ขาดทุนแยกราย leg: realized (ปิดแล้ว) + floating (ยังเปิดอยู่) ─────────
    pnl_by_leg = _fetch_leg_pnl(portfolio_name)
    if pnl_by_leg:
        now = _now_bkk()
        lines.append(f"\n💵 *กำไร/ขาดทุน แยกราย leg:*")
        total_realized = 0.0
        total_floating = 0.0
        sort_key = lambda k: pnl_by_leg[k]["total"] + pnl_by_leg[k]["floating"]
        for leg_id in sorted(pnl_by_leg, key=sort_key, reverse=True):
            d = pnl_by_leg[leg_id]
            key = leg_id.split("-", 1)[1]  # "P13-D" -> "D"
            label = _leg_label(key)
            first_dt = datetime.fromisoformat(d["first_ts"])
            days_elapsed = max((now - first_dt).total_seconds() / 86400.0, 1.0)
            per_day = d["total"] / days_elapsed
            per_month = per_day * 30
            total_realized += d["total"]
            total_floating += d["floating"]
            float_part = f" | ลอยอยู่ `${d['floating']:+.2f}` (ยังไม่ปิด)" if d["floating"] != 0 else ""
            lines.append(
                f"  `{key}` {label}: ปิดแล้ว `${d['total']:+.2f}` "
                f"({d['n_closed']} ไม้){float_part}\n"
                f"      เฉลี่ย/วัน `${per_day:+.2f}` | เฉลี่ย/เดือน `${per_month:+.2f}`"
            )
        lines.append(
            f"\n**รวม realized (ปิดแล้ว): ${total_realized:+.2f}**\n"
            f"**รวม floating (ยังไม่ปิด): ${total_floating:+.2f}**\n"
            f"**รวมทั้งหมด: ${total_realized + total_floating:+.2f}**"
        )
    else:
        lines.append("\n_ยังไม่มีไม้เข้าเลย — รอสัญญาณแรกก่อน_")

    return "\n".join(lines)


async def lts_exit_manager(app):
    """
    Phase 4 Exit Manager for LTS Portfolios
    Runs periodically (e.g. 5s) to check Smart Cutloss and Momentum Stall Exit for LTS.
    """
    import mt5_worker as mt5
    import pandas as pd
    import config
    from bot_log import log_event
    from trailing import _close_position
    
    positions = mt5.positions_get(symbol=config.SYMBOL)
    if not positions:
        return
        
    rates = mt5.copy_rates_from_pos(config.SYMBOL, mt5.TIMEFRAME_M15, 0, 60)
    if rates is None or len(rates) < 50:
        return
        
    df = pd.DataFrame(rates)
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    current_price = df['close'].iloc[-1]
    ema20 = df['ema20'].iloc[-1]
    ema50 = df['ema50'].iloc[-1]
    
    # Pre-calculate Momentum Stall components
    recent_highs = df['high'].iloc[-6:-1]
    recent_lows = df['low'].iloc[-6:-1]
    mult = 100000 if "USD" in config.SYMBOL or "EUR" in config.SYMBOL or "GBP" in config.SYMBOL else 1000
    if config.SYMBOL == "XAUUSD":
        mult = 100
        
    for pos in positions:
        ticket = pos.ticket
        magic = pos.magic
        
        # Check if it's an LTS position (LTS_MAGIC_BASE = 992000)
        if not (magic >= 992000 and magic <= 992999):
            continue
            
        portfolio = f"LTS{magic - 992000}"
        
        is_buy = pos.type == mt5.ORDER_TYPE_BUY
        pos_type = "BUY" if is_buy else "SELL"
        
        # 1. Smart Cutloss Check
        if config.SMART_CUTLOSS_ENABLED.get(portfolio, False):
            should_cut = False
            reason = ""
            if is_buy:
                if current_price < ema50 and ema20 < ema50:
                    should_cut = True
                    reason = "ราคาหลุด EMA50 และเกิด Death Cross (Momentum Reversal)"
            else:
                if current_price > ema50 and ema20 > ema50:
                    should_cut = True
                    reason = "ราคาทะลุ EMA50 และเกิด Golden Cross (Momentum Reversal)"
                    
            if should_cut:
                ok, cp = _close_position(pos, pos_type, "LTS Smart Cut-loss (EMA)")
                if ok:
                    log_event("SMART_CUTLOSS", f"[{portfolio}] Closed {pos_type} {ticket} due to {reason}", ticket=ticket)
                    if app:
                        from notifications import tg
                        await tg(app, f"🛡️ *LTS Smart Cut-loss ทำงาน* [{portfolio}]\nTicket: `{ticket}` ({pos_type})\nเหตุผล: {reason}\nเพื่อรักษาทุนก่อนชน SL")
                continue # Skip momentum check if already closed
                
        # 2. Momentum Stall Check
        if config.MOMENTUM_STALL_EXIT_ENABLED.get(portfolio, False):
            profit_points = (pos.price_current - pos.price_open) * mult
            if not is_buy:
                profit_points = -profit_points
                
            if profit_points >= 150:
                is_stalled = False
                if is_buy:
                    max_recent_high = recent_highs.max()
                    if pos.price_current < max_recent_high:
                        is_stalled = True
                else:
                    min_recent_low = recent_lows.min()
                    if pos.price_current > min_recent_low:
                        is_stalled = True
                        
                if is_stalled:
                    ok, cp = _close_position(pos, pos_type, "LTS Momentum Stall Exit")
                    if ok:
                        log_event("MOMENTUM_STALL", f"[{portfolio}] Closed {pos_type} {ticket} due to Momentum Stall (+{profit_points:.0f} pts)", ticket=ticket)
                        if app:
                            from notifications import tg
                            await tg(app, f"🛑 *LTS Momentum Stall Exit* [{portfolio}]\nTicket: `{ticket}` ({pos_type})\nกำไร: `{profit_points:.0f}` จุด\nเหตุผล: กราฟยึกยัก ไม่ทำยอดใหม่ใน 5 แท่งล่าสุด (M15)")
