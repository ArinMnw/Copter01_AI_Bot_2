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
_sweep_state:      dict[str, str]   = {}  # "SWEEP_LOW" | "SWEEP_HIGH"
_sweep_price:      dict[str, float] = {}  # ราคา swing ที่เป็น reference
_sweep_at:         dict[str, str]   = {}  # เวลา detect (BKK string)
_sweep_ts:         dict[str, int]   = {}  # เวลา detect (unix ของ trigger bar) — ใช้เช็ค expiry
_prev_trend:       dict[str, str]   = {}  # track trend เพื่อ detect change
_prev_last_label:  dict[str, str]   = {}  # track last swing label เพื่อ detect change

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

# จำนวนวินาทีของแต่ละ HTF (ใช้หา M5 bar ที่ cover M1 trigger bar)
_HTF_SECS: dict[str, int] = {
    "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400,
}

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
    # หมดอายุ → reset แล้วคืน None (กัน sweep เก่าค้าง override trend นานเกิน)
    if _sweep_state.get(tf) and _is_expired(tf):
        reset_sweep(tf)
        return None
    return _sweep_state.get(tf)


def get_sweep_info(tf: str) -> dict:
    return {
        "state": _sweep_state.get(tf),
        "price": _sweep_price.get(tf),
        "time":  _sweep_at.get(tf, ""),
    }


def reset_sweep(tf: str, reason: str = "") -> None:
    prev = _sweep_state.get(tf)
    if prev:
        try:
            from bot_log import log_event as _log
            _log("SWEEP_RESET", prev, tf=tf, reason=reason or "-")
        except Exception:
            pass
    _sweep_state.pop(tf, None)
    _sweep_price.pop(tf, None)
    _sweep_at.pop(tf, None)
    _sweep_ts.pop(tf, None)


def reset_all() -> None:
    _sweep_state.clear()
    _sweep_price.clear()
    _sweep_at.clear()
    _sweep_ts.clear()


def update_trend_and_check_reset(tf: str, current_trend: str,
                                  last_label: str = "") -> bool:
    """
    เรียกทุก scan cycle: reset sweep state เมื่อ trend หรือ last swing label เปลี่ยน

    Trend transitions ที่ reset (ทั้งหมด):
      BULL↔BEAR, BULL↔SIDEWAY, BEAR↔SIDEWAY

    Last label transitions ที่ reset (เฉพาะตอน trend = SIDEWAY เท่านั้น):
      HL→HH/LH/LL, LH→HH/HL/LL, HH→LH/HL/LL, LL→LH/HL/HH
      (BULL→BULL หรือ BEAR→BEAR label เปลี่ยน ไม่นับ)

    คืน True ถ้า reset เกิดขึ้น
    """
    prev_trend  = _prev_trend.get(tf)
    prev_label  = _prev_last_label.get(tf, "")

    _prev_trend[tf] = current_trend
    if last_label:
        _prev_last_label[tf] = last_label

    trend_changed = (prev_trend is not None and prev_trend != current_trend)
    label_changed = (
        current_trend == "SIDEWAY"
        and bool(last_label) and bool(prev_label)
        and prev_label != last_label
    )

    if trend_changed or label_changed:
        reason = f"trend_changed:{prev_trend}→{current_trend}" if trend_changed else f"label_changed:{prev_label}→{last_label}"
        reset_sweep(tf, reason=reason)
        return True
    return False


# ── Core Detection ────────────────────────────────────────────────────

def _get_latest_high_swing(d: dict) -> tuple[str, float, int] | None:
    """หา swing HIGH ล่าสุด (HH หรือ LH) ตามเวลา — สำหรับ SWEEP_HIGH"""
    candidates = []
    for lbl in ("HH", "LH"):
        pt = d.get(lbl.lower())
        if pt and pt.get("time") and pt.get("price"):
            candidates.append((lbl, float(pt["price"]), int(pt["time"])))
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[2])


def _get_latest_low_swing(d: dict) -> tuple[str, float, int] | None:
    """หา swing LOW ล่าสุด (HL หรือ LL) ตามเวลา — สำหรับ SWEEP_LOW"""
    candidates = []
    for lbl in ("HL", "LL"):
        pt = d.get(lbl.lower())
        if pt and pt.get("time") and pt.get("price"):
            candidates.append((lbl, float(pt["price"]), int(pt["time"])))
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[2])


def _get_latest_swing(d: dict) -> tuple[str, float, int] | None:
    """[Compat] หา swing ล่าสุดจากทุก 4 ประเภท (ใช้ใน reset tracking)"""
    candidates = []
    for lbl in ("HH", "HL", "LH", "LL"):
        pt = d.get(lbl.lower())
        if pt and pt.get("time") and pt.get("price"):
            candidates.append((lbl, float(pt["price"]), int(pt["time"])))
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[2])


def _detect_both(
    tf: str,
    d: dict,
    rates: list,
    htf_rates_high=None,   # historical HTF rates สำหรับ SWEEP_HIGH
    htf_rates_low=None,    # historical HTF rates สำหรับ SWEEP_LOW
) -> str | None:
    """
    ตรวจทั้ง SWEEP_HIGH และ SWEEP_LOW แยกกันอิสระ:
      - SWEEP_HIGH: ใช้ latest HH/LH swing
      - SWEEP_LOW:  ใช้ latest HL/LL swing

    สาเหตุที่ต้องแยก: swing HIGH และ LOW สามารถสลับกันได้เร็วมากใน M1
    ถ้าดูแค่ "latest swing" เดียวจะพลาดกรณีที่ HIGH swing ถูก sweep แต่
    latest swing เปลี่ยนเป็น LOW type ก่อนที่ HTF จะ confirm เสร็จ

    ถ้าทั้งสองด้านตรงเงื่อนไขพร้อมกัน → เลือก trigger bar ที่ใหม่กว่า
    """
    result_high = None
    result_low  = None

    high_sw = _get_latest_high_swing(d)
    if high_sw:
        lbl, ref_price, ref_time = high_sw
        bars_after = [r for r in rates if int(r["time"]) > ref_time]
        if len(bars_after) >= 2:
            result_high = _check_sweep_high(
                tf, ref_price, ref_time, bars_after, rates, htf_rates_high
            )

    low_sw = _get_latest_low_swing(d)
    if low_sw:
        lbl, ref_price, ref_time = low_sw
        bars_after = [r for r in rates if int(r["time"]) > ref_time]
        if len(bars_after) >= 2:
            result_low = _check_sweep_low(
                tf, ref_price, ref_time, bars_after, rates, htf_rates_low
            )

    # ถ้าทั้งสองด้านไม่ trigger → None
    if not result_high and not result_low:
        return None
    # ถ้าด้านเดียว trigger → คืนด้านนั้น
    if result_high and not result_low:
        return result_high
    if result_low and not result_high:
        return result_low
    # ทั้งสองด้าน trigger → เลือกตาม trigger bar ที่ใหม่กว่า
    high_ts = _sweep_price.get(tf + "_high_ts", 0)
    low_ts  = _sweep_price.get(tf + "_low_ts",  0)
    return result_high if high_ts >= low_ts else result_low


def check_and_update(tf: str) -> str | None:
    """
    ตรวจ sweep conditions (เรียกทุก scan cycle)
    ตรวจทั้ง HIGH-type (HH/LH) และ LOW-type (HL/LL) swing แยกกันอิสระ
    คืน 'SWEEP_LOW' | 'SWEEP_HIGH' | None

    Persistence rule:
      ถ้า sweep active อยู่แล้ว → คงสถานะไว้ (ไม่ reset จาก swing ใหม่)
      reset ได้เฉพาะผ่าน update_trend_and_check_reset
    """
    if not is_enabled():
        return None

    # ถ้า sweep active อยู่แล้ว → คงสถานะ (เว้นแต่หมดอายุ → reset แล้วหาใหม่)
    if _sweep_state.get(tf):
        if _is_expired(tf):
            reset_sweep(tf, reason="expired")
        else:
            return _sweep_state[tf]

    try:
        import hhll_swing as _hs
        d = _hs.get_hhll_data(tf) or {}
    except Exception:
        return None

    if not d:
        return None

    rates = _get_closed_rates(tf, 80)
    if rates is None or len(rates) < 3:
        return None

    return _detect_both(tf, d, list(rates))


def _detect(
    tf: str,
    latest_lbl: str,   # "HH" | "HL" | "LH" | "LL"
    ref_price: float,
    ref_time: int,
    rates: list,
    htf_rates=None,    # historical HTF rates สำหรับ sim (None = ดึง live)
) -> str | None:
    """
    [Internal] Core detection สำหรับ swing เดียว (ใช้ใน check_sweep_at_time)
    HIGH type (HH, LH) → ตรวจ SWEEP_HIGH
    LOW  type (LL, HL) → ตรวจ SWEEP_LOW
    """
    bars_after = [r for r in rates if int(r["time"]) > ref_time]
    if len(bars_after) < 2:
        return None

    if latest_lbl in HIGH_TYPES:
        return _check_sweep_high(tf, ref_price, ref_time, bars_after, rates, htf_rates)
    else:
        return _check_sweep_low(tf, ref_price, ref_time, bars_after, rates, htf_rates)


def _check_sweep_low(
    tf: str, ref_price: float, ref_time: int, bars_after: list, all_rates: list,
    htf_rates=None,
) -> str | None:
    """
    SWEEP_LOW detection (สำหรับ LL หรือ HL เป็น swing ล่าสุด):

    ลำดับการตรวจ: Pattern B ก่อน Pattern A เสมอ
    HTF: ใช้ M5 bar ที่ COVER M1 trigger bar (not any future bar)

    Pattern B – Engulf (ตรวจก่อน):
      แท่ง b: RED (close < open) AND close < ref_price
      แท่ง b+1 และ b+2: ปิดเขียวทั้งสอง
      HTF: M5[cover b].low < ref + M5[next] ปิดเขียว

    Pattern A – Simple Sweep (ตรวจทีหลัง):
      แท่ง b: low < ref_price (any color)
      แท่ง b+1: ปิดเขียว
      HTF: M5[cover b].low < ref + M5[next] ปิดเขียว
    """
    n   = len(bars_after)
    htf = _TF_NEXT.get(tf)
    if htf_rates is None and htf:
        htf_rates = _get_closed_rates(htf, 30)

    for i in range(n - 1):
        b   = bars_after[i]
        nxt = bars_after[i + 1]
        bl        = float(b["low"])
        bo, bc    = float(b["open"]),  float(b["close"])
        no, nc    = float(nxt["open"]), float(nxt["close"])
        b_time    = int(b["time"])

        # ── Pattern B (ก่อน): RED engulf (close < ref) + 2 เขียว ─────────
        # bo > ref_price: bar เปิดเหนือ swing low (ราคายังอยู่เหนือ ref)
        if bo > ref_price and bc < ref_price and bc < bo:
            # bar ปิดต่ำกว่า ref → ถ้า Pattern B ไม่ผ่าน = LL ถูก break แล้ว
            if i + 2 < n:
                nxt2     = bars_after[i + 2]
                n2o, n2c = float(nxt2["open"]), float(nxt2["close"])
                if nc > no and n2c > n2o:
                    if _htf_confirm_at(htf, ref_price, b_time, htf_rates, high=False):
                        _activate("SWEEP_LOW", tf, ref_price, b_time, confirm_ts=int(nxt["time"]))
                        return "SWEEP_LOW"
            return None  # Pattern B failed (bar ปิดต่ำกว่า ref) → LL invalidated

        # LL invalidated: bar ปิดต่ำกว่า ref โดยไม่ผ่าน Pattern B
        if bc < ref_price:
            return None

        # ── Pattern A (ทีหลัง): low < ref + open > ref (sweep จริง) + 1 เขียว ──
        # bo > ref_price: bar ต้องเปิดเหนือ swing low ก่อน แล้วค่อย dip ลงต่ำกว่า
        if bo > ref_price and bl < ref_price and nc > no:
            if _htf_confirm_at(htf, ref_price, b_time, htf_rates, high=False):
                _activate("SWEEP_LOW", tf, ref_price, b_time, confirm_ts=int(nxt["time"]))
                return "SWEEP_LOW"

    return None


def _check_sweep_high(
    tf: str, ref_price: float, ref_time: int, bars_after: list, all_rates: list,
    htf_rates=None,
) -> str | None:
    """
    SWEEP_HIGH detection (สำหรับ HH หรือ LH เป็น swing ล่าสุด):

    ลำดับการตรวจ: Pattern B ก่อน Pattern A เสมอ
    HTF: ใช้ M5 bar ที่ COVER M1 trigger bar (not any future bar)

    Pattern B – Engulf (ตรวจก่อน):
      แท่ง b: GREEN (close > open) AND close > ref_price
      แท่ง b+1 และ b+2: ปิดแดงทั้งสอง
      HTF: M5[cover b].high > ref + M5[next] ปิดแดง

    Pattern A – Simple Sweep (ตรวจทีหลัง):
      แท่ง b: high > ref_price (any color)
      แท่ง b+1: ปิดแดง
      HTF: M5[cover b].high > ref + M5[next] ปิดแดง
    """
    n   = len(bars_after)
    htf = _TF_NEXT.get(tf)
    if htf_rates is None and htf:
        htf_rates = _get_closed_rates(htf, 30)

    for i in range(n - 1):
        b   = bars_after[i]
        nxt = bars_after[i + 1]
        bh        = float(b["high"])
        bo, bc    = float(b["open"]),  float(b["close"])
        no, nc    = float(nxt["open"]), float(nxt["close"])
        b_time    = int(b["time"])

        # ── Pattern B (ก่อน): GREEN engulf (close > ref) + 2 แดง ─────────
        # bo < ref_price: bar เปิดใต้ swing high (ราคายังอยู่ใต้ ref)
        if bo < ref_price and bc > ref_price and bc > bo:
            # bar ปิดสูงกว่า ref → ถ้า Pattern B ไม่ผ่าน = LH ถูก break แล้ว
            if i + 2 < n:
                nxt2     = bars_after[i + 2]
                n2o, n2c = float(nxt2["open"]), float(nxt2["close"])
                if nc < no and n2c < n2o:
                    if _htf_confirm_at(htf, ref_price, b_time, htf_rates, high=True):
                        _activate("SWEEP_HIGH", tf, ref_price, b_time, confirm_ts=int(nxt["time"]))
                        return "SWEEP_HIGH"
            return None  # Pattern B failed (bar ปิดสูงกว่า ref) → LH invalidated

        # LH invalidated: bar ปิดสูงกว่า ref โดยไม่ผ่าน Pattern B
        if bc > ref_price:
            return None

        # ── Pattern A (ทีหลัง): high > ref + open < ref (sweep จริง) + 1 แดง ──
        # bo < ref_price: bar ต้องเปิดใต้ swing high ก่อน แล้วค่อย spike ขึ้นเหนือ
        if bo < ref_price and bh > ref_price and nc < no:
            if _htf_confirm_at(htf, ref_price, b_time, htf_rates, high=True):
                _activate("SWEEP_HIGH", tf, ref_price, b_time, confirm_ts=int(nxt["time"]))
                return "SWEEP_HIGH"

    return None


# ── HTF Confirmation ──────────────────────────────────────────────────

def _htf_confirm_at(htf: str | None, price: float, trigger_time: int,
                    htf_rates, high: bool) -> bool:
    """
    ตรวจ HTF confirmation โดยใช้ M5 bar ที่ COVER M1 trigger_time
    (ป้องกัน M5 bar ไกลๆ ในอนาคตที่ไม่ควรนับ)

    หลักการ:
      หา M5 bar ที่มี time <= trigger_time < time + htf_secs
      → ต้องมี high/low ผ่าน ref_price
      → M5 bar ถัดไปต้องปิดทิศทางที่ถูก (RED สำหรับ HIGH, GREEN สำหรับ LOW)

    high=True  → M5[cover].high > price AND M5[next] ปิดแดง
    high=False → M5[cover].low  < price AND M5[next] ปิดเขียว
    """
    if not htf or htf_rates is None or len(htf_rates) < 2:
        return False

    htf_secs = _HTF_SECS.get(htf, 300)

    # หา index ของ M5 bar ที่ cover trigger_time
    containing_idx = None
    for idx in range(len(htf_rates) - 1):
        rt = int(htf_rates[idx]["time"])
        if rt <= trigger_time < rt + htf_secs:
            containing_idx = idx
            break

    if containing_idx is None:
        return False

    bar_m5  = htf_rates[containing_idx]
    bar_nxt = htf_rates[containing_idx + 1]

    if high:
        return (float(bar_m5["high"])  > price and
                float(bar_nxt["close"]) < float(bar_nxt["open"]))
    else:
        return (float(bar_m5["low"])   < price and
                float(bar_nxt["close"]) > float(bar_nxt["open"]))


# ── MT5 Helpers ───────────────────────────────────────────────────────

def _get_closed_rates(tf: str, n: int = 80):
    """ดึง n แท่งปิดล่าสุด (pos=1 ข้ามแท่งที่กำลัง form)"""
    tf_id = TF_OPTIONS.get(tf)
    if not tf_id or not connect_mt5():
        return None
    return mt5.copy_rates_from_pos(SYMBOL, tf_id, 1, n)


def _activate(state: str, tf: str, price: float, bar_ts: int, confirm_ts: int = 0) -> None:
    _sweep_state[tf] = state
    _sweep_price[tf] = price
    _sweep_ts[tf]    = int(bar_ts)
    bar_str = datetime.fromtimestamp(bar_ts, tz=_BKK).strftime("%H:%M %d-%b-%Y")
    _sweep_at[tf]    = bar_str
    try:
        from bot_log import log_event as _log
        conf_str = datetime.fromtimestamp(confirm_ts, tz=_BKK).strftime("%H:%M %d-%b-%Y") if confirm_ts else "-"
        _log("SWEEP_ACTIVATE", state,
             tf=tf, ref_price=f"{price:.2f}",
             sweep_bar=bar_str, confirm_bar=conf_str)
    except Exception:
        pass


def _is_expired(tf: str) -> bool:
    """เช็คว่า sweep state หมดอายุหรือยัง (ตาม SWEEP_FILTER_EXPIRY_MIN)
    expiry = 0 → ไม่หมดอายุ (behavior เดิม)
    วัดจาก trigger bar time → ปัจจุบัน
    """
    if _cfg_mod is None:
        return False
    expiry_min = int(getattr(_cfg_mod, "SWEEP_FILTER_EXPIRY_MIN", 0) or 0)
    if expiry_min <= 0:
        return False
    trig_ts = _sweep_ts.get(tf, 0)
    if trig_ts <= 0:
        return False
    import time as _t
    age_sec = _t.time() - trig_ts
    return age_sec > expiry_min * 60


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
    end_dt,           # datetime (raw +1h) ของเวลาที่ต้องการตรวจ
    swings: dict,     # {"hh": {price,time}|None, "hl":..., "lh":..., "ll":...}
) -> str | None:
    """
    ใช้สำหรับ simulation: ตรวจ sweep state ณ เวลา end_dt
    swings = dict จาก get_hhll_at() ที่มี hh/hl/lh/ll ครบ
    คืน 'SWEEP_LOW' | 'SWEEP_HIGH' | None

    ตรวจทั้ง HIGH-type (HH/LH) และ LOW-type (HL/LL) แยกกันอิสระ
    เพื่อป้องกันกรณีที่ HIGH swing ถูก sweep แต่ latest swing
    เปลี่ยนเป็น LOW type ก่อนที่ HTF จะ confirm เสร็จ
    """
    if not connect_mt5():
        return None
    tf_id = TF_OPTIONS.get(tf)
    if not tf_id:
        return None

    # ถ้า sweep active อยู่แล้ว → คงสถานะ (persistence rule เหมือน check_and_update)
    if _sweep_state.get(tf):
        return _sweep_state[tf]

    # หา HIGH และ LOW swing แยกกัน
    high_sw = _get_latest_high_swing(swings)
    low_sw  = _get_latest_low_swing(swings)

    if not high_sw and not low_sw:
        return None

    end_adj = end_dt - timedelta(seconds=60)

    # หา start_dt เป็น oldest swing time (เพื่อ fetch rates ครอบคลุมทั้งสอง)
    times = []
    if high_sw: times.append(high_sw[2])
    if low_sw:  times.append(low_sw[2])
    oldest_ref_time = min(times)
    start_dt = datetime.fromtimestamp(oldest_ref_time, tz=_BKK)

    # ดึง rates ของ TF หลัก (ครอบคลุมตั้งแต่ swing เก่าสุดถึง end_adj)
    rates = mt5.copy_rates_range(SYMBOL, tf_id, start_dt, end_adj)
    if rates is None or len(rates) < 3:
        return None

    # ดึง historical HTF rates (ใช้ร่วมกันทั้งสองทิศ)
    htf_rates = None
    htf = _TF_NEXT.get(tf)
    if htf:
        htf_id = TF_OPTIONS.get(htf)
        if htf_id:
            htf_start = start_dt - timedelta(hours=2)
            htf_r = mt5.copy_rates_range(SYMBOL, htf_id, htf_start, end_adj)
            if htf_r is not None and len(htf_r) > 0:
                htf_rates = htf_r

    return _detect_both(tf, swings, list(rates), htf_rates, htf_rates)
