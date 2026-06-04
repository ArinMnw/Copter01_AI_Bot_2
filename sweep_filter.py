# sweep_filter.py
# ──────────────────────────────────────────────────────────────────────
# Sweep Low / Sweep High Filter
#   SWEEP_LOW  → Block SELL, Unblock BUY  (ราคา sweep low แล้ว bounce ขึ้น)
#   SWEEP_HIGH → Block BUY,  Unblock SELL (ราคา sweep high แล้ว reject ลง)
#
# Logic การ detect:
#   ดู "swing ล่าสุดตามเวลา" จากทุก 4 ประเภท (HH / HL / LH / LL):
#     - ถ้า swing ล่าสุดเป็น HIGH type (HH หรือ LH)
#         PRIMARY: แท่งแรกหลัง swing ปิดแดง   → SWEEP_HIGH
#         ALT:     close > swing.price + 2 แดง + HTF red → SWEEP_HIGH
#     - ถ้า swing ล่าสุดเป็น LOW type  (LL หรือ HL)
#         PRIMARY: แท่งแรกหลัง swing ปิดเขียว → SWEEP_LOW
#         ALT:     close < swing.price + 2 เขียว + HTF green → SWEEP_LOW
#
# Reset:  เมื่อ trend เปลี่ยน (update_trend_and_check_reset)
#         หรือตอน detect ไม่เจอ swing → reset state
# TF:     ทุก TF ที่ bot เทรด (M1/M5/M15/M30/H1)
# Config: config.SWEEP_FILTER_ENABLED (toggle via Telegram)
# ──────────────────────────────────────────────────────────────────────

import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone

try:
    from config import TF_OPTIONS, SYMBOL
    from mt5_utils import connect_mt5
    import config as _cfg_mod
except ImportError:
    TF_OPTIONS = {}
    SYMBOL = ""
    _cfg_mod = None
    def connect_mt5(): return False

# ── State per TF ──────────────────────────────────────────────────────
_sweep_state: dict[str, str]   = {}  # "SWEEP_LOW" | "SWEEP_HIGH"
_sweep_price: dict[str, float] = {}  # ราคา swing ที่เป็น reference
_sweep_at:    dict[str, str]   = {}  # เวลา detect (BKK string)
_prev_trend:  dict[str, str]   = {}  # track trend เพื่อ detect change

_BKK = timezone(timedelta(hours=7))

# TF hierarchy สำหรับ alt-trigger check
_TF_NEXT: dict[str, str] = {
    "M1":  "M5",
    "M5":  "M15",
    "M15": "M30",
    "M30": "H1",
    "H1":  "H4",
}

TRADING_TFS = ["M1", "M5", "M15", "M30", "H1"]

# HIGH_TYPES: swing ที่ถือว่าเป็น "จุดสูง" → ตรวจ SWEEP_HIGH
# LOW_TYPES:  swing ที่ถือว่าเป็น "จุดต่ำ" → ตรวจ SWEEP_LOW
HIGH_TYPES = ("HH", "LH")
LOW_TYPES  = ("LL", "HL")


# ── Public API ────────────────────────────────────────────────────────

def is_enabled() -> bool:
    if _cfg_mod is None:
        return False
    return bool(getattr(_cfg_mod, "SWEEP_FILTER_ENABLED", False))


def get_sweep_state(tf: str) -> str | None:
    """คืน 'SWEEP_LOW' | 'SWEEP_HIGH' | None"""
    if not is_enabled():
        return None
    return _sweep_state.get(tf)


def get_sweep_info(tf: str) -> dict:
    return {
        "state": _sweep_state.get(tf),
        "price": _sweep_price.get(tf),
        "time":  _sweep_at.get(tf, ""),
    }


def reset_sweep(tf: str) -> None:
    _sweep_state.pop(tf, None)
    _sweep_price.pop(tf, None)
    _sweep_at.pop(tf, None)


def reset_all() -> None:
    _sweep_state.clear()
    _sweep_price.clear()
    _sweep_at.clear()


def update_trend_and_check_reset(tf: str, current_trend: str) -> bool:
    """
    เรียกทุก scan cycle: ถ้า trend เปลี่ยน → reset sweep state
    คืน True ถ้า reset เกิดขึ้น
    """
    prev = _prev_trend.get(tf)
    changed = (prev is not None and prev != current_trend)
    if changed:
        reset_sweep(tf)
    _prev_trend[tf] = current_trend
    return changed


# ── Core Detection ────────────────────────────────────────────────────

def _get_latest_swing(d: dict) -> tuple[str, float, int] | None:
    """
    หา swing ล่าสุดตามเวลาจากทุก 4 ประเภท (HH/HL/LH/LL)
    คืน (label, price, time) ของ swing ที่ใหม่ที่สุด หรือ None
    """
    candidates = []
    for lbl in ("HH", "HL", "LH", "LL"):
        pt = d.get(lbl.lower())
        if pt and pt.get("time") and pt.get("price"):
            candidates.append((lbl, float(pt["price"]), int(pt["time"])))
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[2])  # newest by time


def check_and_update(tf: str) -> str | None:
    """
    ตรวจ sweep conditions (เรียกทุก scan cycle)
    ใช้ swing ล่าสุดจากทุก 4 ประเภท (HH/HL/LH/LL) ตามเวลา
    คืน 'SWEEP_LOW' | 'SWEEP_HIGH' | None
    """
    if not is_enabled():
        return None

    try:
        import hhll_swing as _hs
        d = _hs.get_hhll_data(tf) or {}
    except Exception:
        return None

    latest = _get_latest_swing(d)
    if not latest:
        reset_sweep(tf)
        return None

    latest_lbl, ref_price, ref_time = latest

    rates = _get_closed_rates(tf, 80)
    if rates is None or len(rates) < 2:
        return None

    result = _detect(tf, latest_lbl, ref_price, ref_time, list(rates))
    if result is None:
        reset_sweep(tf)
    return result


def _detect(
    tf: str,
    latest_lbl: str,   # "HH" | "HL" | "LH" | "LL"
    ref_price: float,
    ref_time: int,
    rates: list,
) -> str | None:
    """
    Core detection ตาม swing ล่าสุด:
      HIGH type (HH, LH) → ตรวจ SWEEP_HIGH
      LOW  type (LL, HL) → ตรวจ SWEEP_LOW
    """
    bars_after = [r for r in rates if int(r["time"]) > ref_time]
    if len(bars_after) < 1:
        return None

    if latest_lbl in HIGH_TYPES:
        return _check_sweep_high(tf, ref_price, ref_time, bars_after, rates)
    else:
        return _check_sweep_low(tf, ref_price, ref_time, bars_after, rates)


def _check_sweep_low(
    tf: str, ref_price: float, ref_time: int, bars_after: list, all_rates: list
) -> str | None:
    """
    SWEEP_LOW detection (สำหรับ LL หรือ HL เป็น swing ล่าสุด):

    PRIMARY: แท่งแรกหลัง swing.time ปิดเขียว → SWEEP_LOW
    ALT:     แท่งปิดต่ำกว่า ref_price + 2 เขียว + HTF sweep → SWEEP_LOW
    """
    # PRIMARY
    first = bars_after[0]
    fo, fc = float(first["open"]), float(first["close"])
    if fc > fo:   # green
        _activate("SWEEP_LOW", tf, ref_price, int(first["time"]))
        return "SWEEP_LOW"

    # ALT
    n = len(bars_after)
    for i in range(n - 2):
        b    = bars_after[i]
        nxt  = bars_after[i + 1]
        nxt2 = bars_after[i + 2]
        bc        = float(b["close"])
        no, nc    = float(nxt["open"]),  float(nxt["close"])
        n2o, n2c  = float(nxt2["open"]), float(nxt2["close"])
        if bc < ref_price and nc > no and n2c > n2o:
            htf = _TF_NEXT.get(tf)
            if htf and _htf_sweep_low(htf, ref_price):
                _activate("SWEEP_LOW", tf, ref_price, int(b["time"]))
                return "SWEEP_LOW"

    return None


def _check_sweep_high(
    tf: str, ref_price: float, ref_time: int, bars_after: list, all_rates: list
) -> str | None:
    """
    SWEEP_HIGH detection (สำหรับ HH หรือ LH เป็น swing ล่าสุด):

    PRIMARY: แท่งแรกหลัง swing.time ปิดแดง → SWEEP_HIGH
    ALT:     แท่งปิดสูงกว่า ref_price + 2 แดง + HTF sweep → SWEEP_HIGH
    """
    # PRIMARY
    first = bars_after[0]
    fo, fc = float(first["open"]), float(first["close"])
    if fc < fo:   # red
        _activate("SWEEP_HIGH", tf, ref_price, int(first["time"]))
        return "SWEEP_HIGH"

    # ALT
    n = len(bars_after)
    for i in range(n - 2):
        b    = bars_after[i]
        nxt  = bars_after[i + 1]
        nxt2 = bars_after[i + 2]
        bc        = float(b["close"])
        no, nc    = float(nxt["open"]),  float(nxt["close"])
        n2o, n2c  = float(nxt2["open"]), float(nxt2["close"])
        if bc > ref_price and nc < no and n2c < n2o:
            htf = _TF_NEXT.get(tf)
            if htf and _htf_sweep_high(htf, ref_price):
                _activate("SWEEP_HIGH", tf, ref_price, int(b["time"]))
                return "SWEEP_HIGH"

    return None


# ── HTF Confirmation ──────────────────────────────────────────────────

def _htf_sweep_high(htf: str, price: float) -> bool:
    """Higher TF มีแท่งที่ High > price AND Close < Open (red = reject)"""
    rates = _get_closed_rates(htf, 30)
    if not rates:
        return False
    return any(float(r["high"]) > price and float(r["close"]) < float(r["open"]) for r in rates)


def _htf_sweep_low(htf: str, price: float) -> bool:
    """Higher TF มีแท่งที่ Low < price AND Close > Open (green = bounce)"""
    rates = _get_closed_rates(htf, 30)
    if not rates:
        return False
    return any(float(r["low"]) < price and float(r["close"]) > float(r["open"]) for r in rates)


# ── MT5 Helpers ───────────────────────────────────────────────────────

def _get_closed_rates(tf: str, n: int = 80):
    """ดึง n แท่งปิดล่าสุด (pos=1 ข้ามแท่งที่กำลัง form)"""
    tf_id = TF_OPTIONS.get(tf)
    if not tf_id or not connect_mt5():
        return None
    return mt5.copy_rates_from_pos(SYMBOL, tf_id, 1, n)


def _activate(state: str, tf: str, price: float, bar_ts: int) -> None:
    _sweep_state[tf] = state
    _sweep_price[tf] = price
    _sweep_at[tf]    = datetime.fromtimestamp(bar_ts, tz=_BKK).strftime("%H:%M %d-%b")


# ── Telegram Display ──────────────────────────────────────────────────

def get_status_text() -> str:
    enabled = is_enabled()
    lines = [f"🔍 *Sweep Filter*: {'✅ ON' if enabled else '❌ OFF'}"]
    for tf in TRADING_TFS:
        state = _sweep_state.get(tf)
        price = _sweep_price.get(tf, 0)
        t     = _sweep_at.get(tf, "")
        if state == "SWEEP_LOW":
            icon   = "🟢 SWEEP\\_LOW"
            effect = "→ Block SELL / Unblock BUY"
        elif state == "SWEEP_HIGH":
            icon   = "🔴 SWEEP\\_HIGH"
            effect = "→ Block BUY / Unblock SELL"
        else:
            icon   = "⬜ ─"
            effect = ""
        p  = f" @ `{price:.2f}`" if price else ""
        ts = f" `({t})`"         if t     else ""
        lines.append(f"  *{tf}*: {icon}{p}{ts} {effect}")
    return "\n".join(lines)


# ── Simulation Helper (historical replay) ────────────────────────────

def check_sweep_at_time(
    tf: str,
    end_dt,           # datetime (BKK) ของเวลาที่ order สร้าง
    swings: dict,     # {"HH": {price,time}|None, "HL":..., "LH":..., "LL":...}
) -> str | None:
    """
    ใช้สำหรับ simulation: ตรวจ sweep state ณ เวลา end_dt
    swings = dict จาก get_hhll_at() ที่มี HH/HL/LH/LL ครบ
    คืน 'SWEEP_LOW' | 'SWEEP_HIGH' | None
    """
    if not connect_mt5():
        return None
    tf_id = TF_OPTIONS.get(tf)
    if not tf_id:
        return None

    # หา swing ล่าสุดจาก swings dict
    latest = _get_latest_swing(swings)
    if not latest:
        return None
    latest_lbl, ref_price, ref_time = latest

    start_dt = datetime.fromtimestamp(ref_time, tz=_BKK)
    end_adj  = end_dt - timedelta(seconds=60)

    rates = mt5.copy_rates_range(SYMBOL, tf_id, start_dt, end_adj)
    if rates is None or len(rates) < 2:
        return None

    return _detect(tf, latest_lbl, ref_price, ref_time, list(rates))
