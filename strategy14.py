"""
strategy14.py — S14 Sweep RSI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pattern BUY (2 sub-patterns, multi ได้):
  ─ Engulf : bar ปิด (close) ต่ำกว่า ref_low
  ─ Sweep  : bar ทำ low ต่ำกว่า ref_low แต่ปิด (close) >= ref_low (ไส้ลงกลับมา)

  ขั้นตอนร่วม:
  1. หา local low ล่าสุดใน lookback window (ไม่บังคับสีแท่ง)
     → 3-bar pivot: low < prev_low AND low < next_low
     → ref bar = local low ที่ index ล่าสุด (ใหม่ที่สุด)
  2. ref_low = low ของ ref bar
  3. ตรวจ current bar (ไม่บังคับสี):
       - low   < ref_low  (sweep ผ่าน ref low)
       - Engulf : close < ref_low  |  Sweep : close >= ref_low
  4. RSI divergence: RSI_red[reject] > RSI_red[ref] (ใช้ RSI แท่งแดงใกล้สุด ≤3 แท่ง)
  5. RSI_red[reject] < 50
  6. TP = nearest swing HIGH ย้อนหลังใน window | RR >= 1:1
  7. SL = reject.low - SL_BUFFER(atr)
  8. Entry MARKET

Pattern SELL (2 sub-patterns, mirror):
  ─ Engulf : bar close > ref_high
  ─ Sweep  : bar high > ref_high แต่ close <= ref_high (ไส้ขึ้นกลับมา)
  ref bar = local high ล่าสุด (ไม่บังคับสีแท่ง, 3-bar pivot)
  RSI_green[reject] < RSI_green[ref] (ใช้ RSI แท่งเขียวใกล้สุด ≤3 แท่ง) | RSI_green > 50
  TP = nearest swing LOW ย้อนหลังใน window | RR >= 1:1
"""

import config
from config import SL_BUFFER
from mt5_utils import calc_atr
from strategy9 import _calc_rsi_values


# ─────────────────────────────────────────────────────────────────────────────
# Reversal bar detection  (same logic as _reversal_trail_override)
# ─────────────────────────────────────────────────────────────────────────────

def _find_bear_reversals(rates):
    """
    หา index ของ red engulf / red rejection ใน rates[1 .. len-2]
    (ข้ามแท่งล่าสุด rates[-1] ซึ่งเป็น reject bar)
    """
    idxs = []
    n = len(rates) - 1
    for i in range(1, n):
        cur_o  = float(rates[i]["open"])
        cur_c  = float(rates[i]["close"])
        cur_l  = float(rates[i]["low"])
        prev_h = float(rates[i - 1]["high"])
        prev_l = float(rates[i - 1]["low"])
        if cur_c < cur_o:
            if cur_c < prev_l:
                idxs.append(i)
            elif cur_l < prev_l and prev_l <= cur_c <= prev_h:
                idxs.append(i)
    return idxs


def _find_bull_reversals(rates):
    """
    หา index ของ green engulf / green rejection ใน rates[1 .. len-2]
    """
    idxs = []
    n = len(rates) - 1
    for i in range(1, n):
        cur_o  = float(rates[i]["open"])
        cur_c  = float(rates[i]["close"])
        cur_h  = float(rates[i]["high"])
        prev_h = float(rates[i - 1]["high"])
        prev_l = float(rates[i - 1]["low"])
        if cur_c > cur_o:
            if cur_c > prev_h:
                idxs.append(i)
            elif cur_h > prev_h and prev_l <= cur_c <= prev_h:
                idxs.append(i)
    return idxs


def _find_local_lows(rates):
    """
    หา index ของแท่งที่เป็น local low (ไม่บังคับสีแท่ง)
    เงื่อนไข (3-bar pivot): low < prev_low AND low < next_low
    ใช้สำหรับ S14 BUY ref bar
    """
    idxs = []
    n = len(rates) - 1          # reject bar อยู่ที่ rates[n]
    for i in range(1, n - 1):   # ต้องมี rates[i-1], rates[i], rates[i+1] ก่อน reject
        cur_l  = float(rates[i]["low"])
        prev_l = float(rates[i - 1]["low"])
        next_l = float(rates[i + 1]["low"])
        if cur_l < prev_l and cur_l < next_l:
            idxs.append(i)
    return idxs


def _find_local_highs(rates):
    """
    หา index ของแท่งที่เป็น local high (ไม่บังคับสีแท่ง)
    เงื่อนไข (3-bar pivot): high > prev_high AND high > next_high
    ใช้สำหรับ S14 SELL ref bar
    """
    idxs = []
    n = len(rates) - 1
    for i in range(1, n - 1):
        cur_h  = float(rates[i]["high"])
        prev_h = float(rates[i - 1]["high"])
        next_h = float(rates[i + 1]["high"])
        if cur_h > prev_h and cur_h > next_h:
            idxs.append(i)
    return idxs


# ─────────────────────────────────────────────────────────────────────────────
# Pivot RSI helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pivot_rsi_buy(rates, rsi_vals, idx):
    """
    BUY: ต้องการ RSI ของแท่งแดงใกล้ที่สุด
    ค้นหาย้อนหลังจาก idx สูงสุด 3 แท่ง
    ถ้าไม่พบแท่งแดงเลย → fallback ใช้ rsi_vals[idx]
    """
    for j in range(idx, max(idx - 3, -1), -1):
        if j >= 0 and float(rates[j]["close"]) < float(rates[j]["open"]):
            return rsi_vals[j]
    return rsi_vals[idx]


def _pivot_rsi_sell(rates, rsi_vals, idx):
    """
    SELL: ต้องการ RSI ของแท่งเขียวใกล้ที่สุด
    ค้นหาย้อนหลังจาก idx สูงสุด 3 แท่ง
    ถ้าไม่พบแท่งเขียวเลย → fallback ใช้ rsi_vals[idx]
    """
    for j in range(idx, max(idx - 3, -1), -1):
        if j >= 0 and float(rates[j]["close"]) > float(rates[j]["open"]):
            return rsi_vals[j]
    return rsi_vals[idx]


# ─────────────────────────────────────────────────────────────────────────────
# TP จาก swing highs/lows ย้อนหลังใน window
# ─────────────────────────────────────────────────────────────────────────────

def _build_zz(rates, left: int = 5, right: int = 5):
    """
    สร้าง zigzag จาก rates window
    Port จาก HHLLStrategy.mq5 IsPH / IsPL / BuildZZ
    rates: forward-indexed (rates[0]=oldest, rates[-1]=newest)
    คืน list ของ {"price", "time", "dir", "idx"}  dir: +1=high -1=low
    """
    n = len(rates)

    def is_ph(i):
        if i - left < 0 or i + right >= n:
            return False
        h = float(rates[i]["high"])
        for j in range(i - left, i):
            if float(rates[j]["high"]) >= h:  return False   # left: strict <
        for j in range(i + 1, i + right + 1):
            if float(rates[j]["high"]) >  h:  return False   # right: <=
        return True

    def is_pl(i):
        if i - left < 0 or i + right >= n:
            return False
        l = float(rates[i]["low"])
        for j in range(i - left, i):
            if float(rates[j]["low"]) <=  l: return False    # left: strict >
        for j in range(i + 1, i + right + 1):
            if float(rates[j]["low"]) <   l: return False    # right: >=
        return True

    zz = []
    for i in range(left, n - right):
        ph = is_ph(i)
        pl = is_pl(i)
        if not ph and not pl:
            continue
        if ph and pl:                              # ทั้งคู่ → เลือกตาม direction ก่อนหน้า
            if zz and zz[-1]["dir"] == 1: ph = False
            else:                          pl = False

        p = float(rates[i]["high"]) if ph else float(rates[i]["low"])
        d = 1 if ph else -1

        # consecutive same-direction → skip ถ้าตัวใหม่ extreme น้อยกว่า
        if zz and zz[-1]["dir"] == d:
            if d ==  1 and p <  zz[-1]["price"]: continue
            if d == -1 and p >  zz[-1]["price"]: continue

        # alternating แต่ price อยู่ผิดด้าน
        if zz:
            if d == -1 and p > zz[-1]["price"]: continue
            if d ==  1 and p < zz[-1]["price"]: continue

        zz.append({"price": p, "time": int(rates[i]["time"]),
                   "dir": d, "idx": i})
    return zz


def _classify_pt(zz: list, k: int):
    """
    จำแนก zigzag point k เป็น HH / HL / LH / LL หรือ None
    Port จาก HHLLStrategy.mq5 ClassifyPt
    """
    if k < 4:
        return None
    a  = zz[k]["price"]
    ad = zz[k]["dir"]
    opp = -ad
    b = c = d = e = 0.0
    step = 0
    need = opp
    for j in range(k - 1, -1, -1):
        if zz[j]["dir"] != need:
            continue
        if   step == 0: b = zz[j]["price"]; need = ad
        elif step == 1: c = zz[j]["price"]; need = opp
        elif step == 2: d = zz[j]["price"]; need = ad
        elif step == 3: e = zz[j]["price"]
        step += 1
        if step == 4:
            break
    if step < 4:
        return None

    is_hh = (a > b) and (a > c) and (c > b) and (c > d)
    is_ll = (a < b) and (a < c) and (c < b) and (c < d)
    is_hl = ((a >= c and b > c and b > d and d > c and d > e) or
             (a < b and a > c and b < d))
    is_lh = ((a <= c and b < c and b < d and d < c and d < e) or
             (a > b and a < c and b > d))

    if is_hh: return "HH"
    if is_ll: return "LL"
    if is_hl: return "HL"
    if is_lh: return "LH"
    return None


def _tp_from_window(rates, signal: str, entry: float, sl: float, pivot_n: int = 5):
    """
    หา TP จาก HH/LH (BUY) หรือ HL/LL (SELL) ใน rates window
    ใช้ logic เดียวกับ HHLLStrategy.mq5 (Left=Right=pivot_n)

    BUY  → nearest HH หรือ LH เหนือ entry | RR >= 1:1
    SELL → nearest HL หรือ LL ต่ำกว่า entry | RR >= 1:1
    """
    risk = abs(entry - sl)
    if risk <= 0:
        return None

    zz = _build_zz(rates, left=pivot_n, right=pivot_n)
    if len(zz) < 5:
        return None

    cands = []
    for k in range(len(zz)):
        label = _classify_pt(zz, k)
        if label is None:
            continue
        p = zz[k]["price"]
        if signal == "BUY" and label in ("HH", "LH"):
            if p > entry and (p - entry) >= risk:
                cands.append(p)
        elif signal == "SELL" and label in ("HL", "LL"):
            if p < entry and (entry - p) >= risk:
                cands.append(p)

    if not cands:
        return None
    return round(min(cands), 2) if signal == "BUY" else round(max(cands), 2)


# ─────────────────────────────────────────────────────────────────────────────
# BUY — Engulf & Sweep
# ─────────────────────────────────────────────────────────────────────────────

def _build_buy_results(rates, rsi_vals, tf: str, tp_rates=None) -> list:
    """
    ตรวจ S14 BUY ทั้ง Engulf และ Sweep patterns

    ขั้นตอน:
    1. หา local low ล่าสุดใน lookback window (ไม่บังคับสีแท่ง, 3-bar pivot)
       ref bar = local low ที่ index ล่าสุด (ถ้า S14_LL_USE_HHLL ให้รวม HHLL swing low ด้วย)
    2. ref_low = low ของ ref bar
    3. reject bar (rates[-1]) ต้องมี low < ref_low (ไม่บังคับสี)
    4. Engulf : close < ref_low
       Sweep  : close >= ref_low  (ไส้ลงแต่ปิดกลับมา)
    5. RSI divergence: RSI_red[reject] > RSI_red[ref] (ใช้ RSI แท่งแดงใกล้สุด ≤3 แท่ง)
       และ RSI_red[reject] < 50
    """
    want_engulf = getattr(config, "S14_ENGULF", True)
    want_sweep  = getattr(config, "S14_SWEEP",  True)
    if not want_engulf and not want_sweep:
        return []

    if len(rates) < 4:
        return []

    # ── 1. รวม candidate reference points ─────────────────────────
    # แต่ละ candidate: {"idx": int, "time": int, "low": float, "source": str}
    candidates = []

    reject_idx = len(rates) - 1
    local_low_idxs = _find_local_lows(rates)
    if local_low_idxs:
        # กรองเฉพาะ local lows ที่ห่างจาก reject >= 2 แท่ง
        valid_lows = [i for i in local_low_idxs if reject_idx - i >= 2]
        if valid_lows:
            # ref bar = local low ล่าสุด (index สูงสุด)
            ll_idx = max(valid_lows)
            candidates.append({
                "idx":    ll_idx,
                "time":   int(rates[ll_idx]["time"]),
                "low":    float(rates[ll_idx]["low"]),
                "source": "local_low",
            })

    if getattr(config, "S14_LL_USE_HHLL", False):
        try:
            from hhll_swing import get_swing_hl_pts
            _, sl_pt = get_swing_hl_pts(tf)   # sl_pt = HL หรือ LL อันใหม่กว่า
            if sl_pt:
                sl_time = int(sl_pt["time"])
                # หา bar index ใน window ที่ตรงกับ timestamp นี้
                for i in range(len(rates) - 1):
                    if int(rates[i]["time"]) == sl_time:
                        candidates.append({
                            "idx":    i,
                            "time":   sl_time,
                            "low":    float(sl_pt["price"]),
                            "source": sl_pt.get("label", "hhll_sl"),
                        })
                        break
        except Exception:
            pass

    if not candidates:
        return []

    # ── 2. เลือก candidate ที่ล่าสุด (time สูงสุด) ──────────────
    ref     = max(candidates, key=lambda c: c["time"])
    ref_idx = ref["idx"]
    ref_low = ref["low"]
    ref_rsi = _pivot_rsi_buy(rates, rsi_vals, ref_idx)   # pivot RSI (แดงใกล้สุด)
    if ref_rsi is None:
        return []

    # ── 2b. safety: ref กับ reject ต้องห่างกันอย่างน้อย 2 แท่ง ──
    if reject_idx - ref_idx < 2:
        return []

    # ── 3. ตรวจ reject bar (rates[-1]) ────────────────────────────
    cur   = rates[-1]
    cur_o = float(cur["open"])
    cur_c = float(cur["close"])
    cur_l = float(cur["low"])

    # low ต้องต่ำกว่า ref_low (ไม่บังคับสี)
    if cur_l >= ref_low:
        return []

    # RSI divergence (pivot RSI แดง)
    cur_rsi = _pivot_rsi_buy(rates, rsi_vals, reject_idx)
    if cur_rsi is None or cur_rsi <= ref_rsi or cur_rsi >= 50.0:
        return []

    # ATR / SL — True Range + RMA (ตรงกับ ATR_TrueRange.mq5)
    atr   = calc_atr(rates, 14)
    sl    = round(cur_l - SL_BUFFER(atr), 2)

    src_label = f"({ref['source']})"
    results   = []

    # ── Engulf: close < ref_low ────────────────────────────────────
    if want_engulf and cur_c < ref_low:
        entry = round(cur_c, 2)
        if entry > sl:
            tp = _tp_from_window(tp_rates if tp_rates else rates, "BUY", entry, sl)
            if tp is not None:
                reason = (
                    f"[Engulf] ปิดต่ำกว่า ref {src_label}\n"
                    f"ref: `{ref_low:.2f}` | RSI ref: `{ref_rsi:.2f}`\n"
                    f"Red Engulf: L=`{cur_l:.2f}` C=`{cur_c:.2f}` < ref=`{ref_low:.2f}`\n"
                    f"RSI Div: reject=`{cur_rsi:.2f}` > ref=`{ref_rsi:.2f}` (< 50)\n"
                    f"Entry: `{entry:.2f}` | SL: `{sl:.2f}` | TP: `{tp:.2f}`"
                )
                results.append({
                    "signal":      "BUY",
                    "entry":       entry,
                    "sl":          sl,
                    "tp":          tp,
                    "pattern":     "ท่าที่ 14 Sweep RSI \U0001f7e2 BUY — Engulf",
                    "reason":      reason,
                    "order_mode":  "market",
                    "entry_label": "BUY MARKET (Engulf)",
                    "sub_pattern": "engulf",
                    "ref_low":     ref_low,
                    "ref_source":  ref["source"],
                    "rsi_at_ref":  round(ref_rsi, 2),
                    "rsi_at_rej":  round(cur_rsi, 2),
                })

    # ── Sweep: open > ref_low, low < ref_low, close >= ref_low ───────
    if want_sweep and cur_o > ref_low and cur_c >= ref_low:
        entry = round(cur_c, 2)
        if entry > sl:
            tp = _tp_from_window(tp_rates if tp_rates else rates, "BUY", entry, sl)
            if tp is not None:
                reason = (
                    f"[Sweep] ไส้ลงต่ำกว่า ref แต่ปิดกลับมา {src_label}\n"
                    f"ref: `{ref_low:.2f}` | RSI ref: `{ref_rsi:.2f}`\n"
                    f"Red Sweep: L=`{cur_l:.2f}` < ref=`{ref_low:.2f}` | C=`{cur_c:.2f}` >= ref\n"
                    f"RSI Div: reject=`{cur_rsi:.2f}` > ref=`{ref_rsi:.2f}` (< 50)\n"
                    f"Entry: `{entry:.2f}` | SL: `{sl:.2f}` | TP: `{tp:.2f}`"
                )
                results.append({
                    "signal":      "BUY",
                    "entry":       entry,
                    "sl":          sl,
                    "tp":          tp,
                    "pattern":     "ท่าที่ 14 Sweep RSI \U0001f7e2 BUY — Sweep",
                    "reason":      reason,
                    "order_mode":  "market",
                    "entry_label": "BUY MARKET (Sweep)",
                    "sub_pattern": "sweep",
                    "ref_low":     ref_low,
                    "ref_source":  ref["source"],
                    "rsi_at_ref":  round(ref_rsi, 2),
                    "rsi_at_rej":  round(cur_rsi, 2),
                })

    return results


# ─────────────────────────────────────────────────────────────────────────────
# SELL — Engulf & Sweep
# ─────────────────────────────────────────────────────────────────────────────

def _build_sell_results(rates, rsi_vals, tf: str, tp_rates=None) -> list:
    """
    ตรวจ S14 SELL ทั้ง Engulf และ Sweep patterns (mirror ของ BUY)

    ขั้นตอน:
    1. หา local high ล่าสุดใน lookback window (ไม่บังคับสีแท่ง, 3-bar pivot)
       ref bar = local high ที่ index ล่าสุด (ถ้า S14_LL_USE_HHLL ให้รวม HHLL swing high ด้วย)
    2. ref_high = high ของ ref bar
    3. reject bar (rates[-1]) ต้องมี high > ref_high (ไม่บังคับสี)
    4. Engulf : close > ref_high
       Sweep  : close <= ref_high  (ไส้ขึ้นแต่ปิดกลับมา)
    5. RSI divergence: RSI_green[reject] < RSI_green[ref] (ใช้ RSI แท่งเขียวใกล้สุด ≤3 แท่ง)
       และ RSI_green[reject] > 50
    """
    want_engulf = getattr(config, "S14_ENGULF", True)
    want_sweep  = getattr(config, "S14_SWEEP",  True)
    if not want_engulf and not want_sweep:
        return []

    if len(rates) < 4:
        return []

    # ── 1. รวม candidate reference points ─────────────────────────
    candidates = []

    reject_idx = len(rates) - 1
    local_high_idxs = _find_local_highs(rates)
    if local_high_idxs:
        # กรองเฉพาะ local highs ที่ห่างจาก reject >= 2 แท่ง
        valid_highs = [i for i in local_high_idxs if reject_idx - i >= 2]
        if valid_highs:
            # ref bar = local high ล่าสุด (index สูงสุด)
            latest_high = max(valid_highs)
            candidates.append({
                "idx":    latest_high,
                "time":   int(rates[latest_high]["time"]),
                "high":   float(rates[latest_high]["high"]),
                "source": "local_high",
            })

    if getattr(config, "S14_LL_USE_HHLL", False):
        try:
            from hhll_swing import get_swing_hl_pts
            sh_pt, _ = get_swing_hl_pts(tf)   # sh_pt = HH หรือ LH อันใหม่กว่า
            if sh_pt:
                sh_time = int(sh_pt["time"])
                for i in range(len(rates) - 1):
                    if int(rates[i]["time"]) == sh_time:
                        candidates.append({
                            "idx":    i,
                            "time":   sh_time,
                            "high":   float(sh_pt["price"]),
                            "source": sh_pt.get("label", "hhll_sh"),
                        })
                        break
        except Exception:
            pass

    if not candidates:
        return []

    # ── 2. เลือก candidate ที่ล่าสุดที่สุด (time สูงสุด) ─────────
    ref      = max(candidates, key=lambda c: c["time"])
    ref_idx  = ref["idx"]
    ref_high = ref["high"]
    ref_rsi  = _pivot_rsi_sell(rates, rsi_vals, ref_idx)  # pivot RSI (เขียว)
    if ref_rsi is None:
        return []

    # ── 2b. safety: ref กับ reject ต้องห่างกันอย่างน้อย 2 แท่ง ──
    if reject_idx - ref_idx < 2:
        return []

    # ── 3. ตรวจ reject bar (rates[-1]) ────────────────────────────
    cur   = rates[-1]
    cur_o = float(cur["open"])
    cur_c = float(cur["close"])
    cur_h = float(cur["high"])

    # high ต้องสูงกว่า ref_high (ไม่บังคับสี)
    if cur_h <= ref_high:
        return []

    # RSI divergence (pivot RSI เขียว)
    cur_rsi = _pivot_rsi_sell(rates, rsi_vals, reject_idx)
    if cur_rsi is None or cur_rsi >= ref_rsi or cur_rsi <= 50.0:
        return []

    atr   = calc_atr(rates, 14)   # True Range + RMA (ตรงกับ ATR_TrueRange.mq5)
    sl    = round(cur_h + SL_BUFFER(atr), 2)

    src_label = f"({ref['source']})"
    results   = []

    # ── Engulf: close > ref_high ───────────────────────────────────
    if want_engulf and cur_c > ref_high:
        entry = round(cur_c, 2)
        if entry < sl:
            tp = _tp_from_window(tp_rates if tp_rates else rates, "SELL", entry, sl)
            if tp is not None:
                reason = (
                    f"[Engulf] ปิดสูงกว่า ref {src_label}\n"
                    f"ref: `{ref_high:.2f}` | RSI ref: `{ref_rsi:.2f}`\n"
                    f"Green Engulf: H=`{cur_h:.2f}` C=`{cur_c:.2f}` > ref=`{ref_high:.2f}`\n"
                    f"RSI Div: reject=`{cur_rsi:.2f}` < ref=`{ref_rsi:.2f}` (> 50)\n"
                    f"Entry: `{entry:.2f}` | SL: `{sl:.2f}` | TP: `{tp:.2f}`"
                )
                results.append({
                    "signal":      "SELL",
                    "entry":       entry,
                    "sl":          sl,
                    "tp":          tp,
                    "pattern":     "ท่าที่ 14 Sweep RSI \U0001f534 SELL — Engulf",
                    "reason":      reason,
                    "order_mode":  "market",
                    "entry_label": "SELL MARKET (Engulf)",
                    "sub_pattern": "engulf",
                    "ref_high":    ref_high,
                    "ref_source":  ref["source"],
                    "rsi_at_ref":  round(ref_rsi, 2),
                    "rsi_at_rej":  round(cur_rsi, 2),
                })

    # ── Sweep: open < ref_high, high > ref_high, close <= ref_high ───
    if want_sweep and cur_o < ref_high and cur_c <= ref_high:
        entry = round(cur_c, 2)
        if entry < sl:
            tp = _tp_from_window(tp_rates if tp_rates else rates, "SELL", entry, sl)
            if tp is not None:
                reason = (
                    f"[Sweep] ไส้ขึ้นสูงกว่า ref แต่ปิดกลับมา {src_label}\n"
                    f"ref: `{ref_high:.2f}` | RSI ref: `{ref_rsi:.2f}`\n"
                    f"Green Sweep: H=`{cur_h:.2f}` > ref=`{ref_high:.2f}` | C=`{cur_c:.2f}` <= ref\n"
                    f"RSI Div: reject=`{cur_rsi:.2f}` < ref=`{ref_rsi:.2f}` (> 50)\n"
                    f"Entry: `{entry:.2f}` | SL: `{sl:.2f}` | TP: `{tp:.2f}`"
                )
                results.append({
                    "signal":      "SELL",
                    "entry":       entry,
                    "sl":          sl,
                    "tp":          tp,
                    "pattern":     "ท่าที่ 14 Sweep RSI \U0001f534 SELL — Sweep",
                    "reason":      reason,
                    "order_mode":  "market",
                    "entry_label": "SELL MARKET (Sweep)",
                    "sub_pattern": "sweep",
                    "ref_high":    ref_high,
                    "ref_source":  ref["source"],
                    "rsi_at_ref":  round(ref_rsi, 2),
                    "rsi_at_rej":  round(cur_rsi, 2),
                })

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def strategy_14(rates, tf: str = ""):
    """
    S14 Sweep RSI

    Returns
    -------
    {"signal": "BUY"|"SELL"|"MULTI"|"WAIT", ...}
    MULTI → {"signal": "MULTI", "orders": [result, ...]}
    """
    period   = int(getattr(config, "S14_RSI_PERIOD",        14))
    applied  = str(getattr(config, "S14_RSI_APPLIED_PRICE", "close"))
    lookback = int(getattr(config, "S14_REVERSAL_LOOKBACK", 50))

    min_bars = period + lookback + 5
    if len(rates) < min_bars:
        return {
            "signal": "WAIT",
            "reason": f"S14: ข้อมูลไม่พอ (ต้องการ {min_bars} มี {len(rates)})",
        }

    full_rates = list(rates)                                    # ทั้งหมดสำหรับ TP (HHLL)
    window     = list(rates[-(lookback + period + 5):])        # 69 bars สำหรับ RSI/signal
    rsi_vals   = _calc_rsi_values(window, period=period, applied_price=applied)

    all_results = []
    all_results.extend(_build_buy_results(window, rsi_vals, tf, tp_rates=full_rates))
    all_results.extend(_build_sell_results(window, rsi_vals, tf, tp_rates=full_rates))

    if not all_results:
        return {"signal": "WAIT", "reason": "S14: ไม่พบ Sweep RSI setup"}

    if len(all_results) == 1:
        return all_results[0]

    # multi (เช่น BUY Engulf + BUY Sweep บน bar เดียวกัน — ต้องเกิดพร้อมกัน)
    return {"signal": "MULTI", "orders": all_results}
