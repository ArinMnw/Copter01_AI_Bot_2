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
        # removed duplicate condition
            if zz and zz[-1]["dir"] == 1: ph = False
            else:                          pl = False

        p = float(rates[i]["high"]) if ph else float(rates[i]["low"])
        d = 1 if ph else -1

        if zz and zz[-1]["dir"] == d:
            if d ==  1 and p <  zz[-1]["price"]: continue
            if d == -1 and p >  zz[-1]["price"]: continue

        if zz:
            if d == -1 and p > zz[-1]["price"]: continue
            if d ==  1 and p < zz[-1]["price"]: continue

        zz.append({"price": p, "time": int(rates[i]["time"]),
                   "dir": d, "idx": i})
    return zz


def _classify_pt(zz: list, k: int):
    """
    จำแนก zigzag point k
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
    หา TP จาก HH/LH (BUY) หรือ HL/LL (SELL)
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


# Higher TF sweep validation (hardcoded list, no extra config)
S14_HIGHER_TF_CHECK = ["M5", "M15"]

def _higher_tf_sweep_valid(current_tf, reject_time, is_buy):
    """Check higher TF sweep patterns around reject_time.
    Returns True if all matching higher TF sweeps satisfy the one‑bar color rule.
    If no higher TF sweep matches the time, returns True (no restriction)."""
    import MetaTrader5 as mt5
    from datetime import timedelta
    for tf in S14_HIGHER_TF_CHECK:
        if tf == current_tf:
            continue
        try:
            tf_const = getattr(mt5, f"TIMEFRAME_{tf.upper()}")
        except Exception:
            continue
        start_ts = int((reject_time - timedelta(minutes=2)).timestamp())
        end_ts   = int((reject_time + timedelta(minutes=2)).timestamp())
        rates = mt5.copy_rates_range(mt5.symbol_info(current_tf).name if hasattr(mt5, 'symbol_info') else None, tf_const, start_ts, end_ts)
        if rates is None or len(rates) == 0:
            continue
        rates = list(rates)
        idx = None
        for i, r in enumerate(rates):
            if int(r["time"]) == int(reject_time.timestamp()):
                idx = i
                break
        if idx is None:
            continue
        expected_color = "red" if is_buy else "green"
        if not _next_n_bar_colors(rates, idx, 1, expected_color):
            return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# HTF and mapping details
# ─────────────────────────────────────────────────────────────────────────────

TF_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
}

def _get_s14_htf(tf_name: str) -> str:
    mapping = {
        "M1": "M5",
        "M5": "M15",
        "M15": "H1",
        "M30": "H4",
        "H1": "H4",
        "H4": "D1"
    }
    return mapping.get(tf_name, "M5")

def _get_next_std_tf(tf_name: str) -> str:
    tfs = ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1"]
    try:
        idx = tfs.index(tf_name)
        if idx < len(tfs) - 1:
            return tfs[idx + 1]
    except ValueError:
        pass
    return "M5"

def _is_sec_htf_currently_sweep(rates, tf_name: str, sec_htf_name: str, ref_level: float, is_buy: bool) -> bool:
    tf_secs = TF_SECONDS.get(tf_name, 60)
    sec_htf_secs = TF_SECONDS.get(sec_htf_name, 1800)
    next_bar_time = int(rates[-1]["time"]) + tf_secs
    sec_htf_start_time = ((next_bar_time - 1) // sec_htf_secs) * sec_htf_secs
    sub_rates = [r for r in rates if int(r["time"]) >= sec_htf_start_time]
    if not sub_rates:
        return False
    if is_buy:
        lowest_low = min(float(r["low"]) for r in sub_rates)
        return lowest_low < ref_level
    else:
        highest_high = max(float(r["high"]) for r in sub_rates)
        return highest_high > ref_level

def _get_htf_bar(tf_name: str, target_time: int, htf_rates_lookup: dict = None):
    """
    คืนค่า dict ของ HTF bar ที่ start_time == target_time
    ถ้ามี htf_rates_lookup ให้ดึงจาก lookup
    ถ้าไม่มี ให้ copy_rates_range จาก MT5
    """
    if htf_rates_lookup is not None:
        return htf_rates_lookup.get(target_time)

    # Live bot case:
    try:
        import MetaTrader5 as mt5
        htf = _get_s14_htf(tf_name)
        htf_const = getattr(mt5, f"TIMEFRAME_{htf.upper()}")
        rates_raw = mt5.copy_rates_range(config.SYMBOL, htf_const, target_time, target_time + 10)
        if rates_raw is not None and len(rates_raw) > 0:
            r = rates_raw[0]
            return {
                "time": int(r["time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"])
            }
    except Exception:
        pass
    return None

# ─────────────────────────────────────────────────────────────────────────────
# BUY — Engulf & Sweep
# ─────────────────────────────────────────────────────────────────────────────

def _build_buy_results(rates, rsi_vals, tf: str, tp_rates=None, htf_rates_lookup: dict = None) -> list:
    """
    ตรวจ S14 BUY ทั้ง Engulf และ Sweep patterns โดยใช้ confirmation bars:
    - Sweep: rates[-2] is sweep low, rates[-1] is GREEN confirm bar. Enter on next bar open (which is rates[-1]['close']).
    - Engulf: rates[i] is engulf low, rates[i+1], rates[i+2] are GREEN confirm bars, and HTF bar closes RED (or secondary HTF is sweep). Enter on next HTF bar.
    """
    want_swing        = getattr(config, "S14_SWEEP_SWING",  True)
    want_engulf_swing = getattr(config, "S14_ENGULF_SWING", True)
    want_sweep        = getattr(config, "S14_SWEEP_RETURN", True)
    if not want_swing and not want_engulf_swing and not want_sweep:
        return []

    if len(rates) < 6:
        return []

    results = []

    def get_ref_low_list(setup_idx, use_hhll=False):
        candidates = []
        if not use_hhll:
            local_low_idxs = _find_local_lows(rates)
            if local_low_idxs:
                valid_lows = [idx for idx in local_low_idxs if setup_idx - idx >= 2]
                if valid_lows:
                    ll_idx = max(valid_lows)
                    candidates.append({
                        "idx":    ll_idx,
                        "time":   int(rates[ll_idx]["time"]),
                        "low":    float(rates[ll_idx]["low"]),
                        "source": "local_low",
                    })
        else:
            try:
                import hhll_swing
                data = hhll_swing.get_hhll_data(tf)
                pts = []
                for k in ["hl", "ll", "prev_hl", "prev_ll"]:
                    pt = data.get(k)
                    if pt:
                        pts.append(pt)
                for pt in pts:
                    pt_time = int(pt["time"])
                    for idx in range(len(rates)):
                        if idx < setup_idx - 1 and int(rates[idx]["time"]) == pt_time:
                            candidates.append({
                                "idx":    idx,
                                "time":   pt_time,
                                "low":    float(pt["price"]),
                                "source": pt.get("label", "hhll_sl"),
                            })
                            break
            except Exception:
                pass
        if not candidates:
            return []
        newest = max(candidates, key=lambda c: c["time"])
        active_refs = [newest]
        if newest["source"] != "LL":
            ll_cands = [c for c in candidates if c["source"] == "LL"]
            if ll_cands:
                latest_ll = max(ll_cands, key=lambda c: c["time"])
                if latest_ll["time"] != newest["time"]:
                    active_refs.append(latest_ll)
        return active_refs

    # ── 2. ตรวจ Sweep (รอ confirm bar เขียวหลัง sweep จบ) ─────────────────────
    # want_swing  = HHLL swing ref  → BSS/SSS
    # want_sweep  = local_low ref   → BRS/SRS
    if (want_swing or want_sweep) and len(rates) >= 3:
        confirm_idx = len(rates) - 1
        sweep_idx   = len(rates) - 2
        confirm_bar = rates[confirm_idx]
        sweep_bar   = rates[sweep_idx]
        co, cc = float(confirm_bar["open"]), float(confirm_bar["close"])

        if cc > co:  # confirm bar ต้องเขียว
            for _use_hhll, _active, _pat, _label, _sub in [
                (True,  want_swing,  "ท่าที่ 14 Sweep RSI 🟢 BUY — Sweep Swing",    "BUY MARKET (Sweep Swing)",    "swing"),
                (False, want_sweep,  "ท่าที่ 14 Sweep RSI 🟢 BUY — Sweep กลับตัว", "BUY MARKET (Sweep กลับตัว)", "sweep"),
            ]:
                if not _active:
                    continue
                ref_list = get_ref_low_list(sweep_idx, use_hhll=_use_hhll)
                for ref in ref_list:
                    ref_idx = ref["idx"]
                    ref_low = ref["low"]
                    ref_rsi = _pivot_rsi_buy(rates, rsi_vals, ref_idx)

                    if (ref_rsi is not None or not getattr(config, "S14_RSI_DIV_ENABLED", True)) and sweep_idx - ref_idx >= 2:
                        # ref_low invalidation: ถ้ามีแท่งระหว่าง ref กับ sweep ปิดต่ำกว่า ref → LL broken
                        if any(float(r["close"]) < ref_low for r in rates[ref_idx + 1:sweep_idx]):
                            continue

                        s_low   = float(sweep_bar["low"])
                        s_open  = float(sweep_bar["open"])
                        s_close = float(sweep_bar["close"])

                        if s_low < ref_low and s_open > ref_low and s_close > ref_low:
                            passed_rsi = True
                            s_rsi = _pivot_rsi_buy(rates, rsi_vals, sweep_idx)
                            if getattr(config, "S14_RSI_DIV_ENABLED", True):
                                _rsi_min_diff = float(getattr(config, "S14_RSI_MIN_DIFF", 1.0))
                                if s_rsi is None or s_rsi >= 50.0 or (s_rsi - ref_rsi) <= _rsi_min_diff:
                                    passed_rsi = False
                            if passed_rsi:
                                entry = round(cc, 2)
                                sl    = round(s_low - SL_BUFFER(calc_atr(rates, 14)), 2)
                                if entry > sl:
                                    tp = _tp_from_window(tp_rates if tp_rates else rates, "BUY", entry, sl)
                                    if tp is not None:
                                        reason = (
                                            f"[Sweep] Sweep low + confirm GREEN\n"
                                            f"ref: `{ref_low:.2f}` ({ref['source']}) | RSI ref: `{ref_rsi:.2f}`\n"
                                            f"Sweep Bar: L=`{s_low:.2f}` < ref=`{ref_low:.2f}` | C=`{s_close:.2f}` >= ref\n"
                                            f"Confirm: C=`{cc:.2f}` (GREEN)\n"
                                            f"RSI Div: reject=`{s_rsi:.2f}` > ref=`{ref_rsi:.2f}` (< 50)\n"
                                            f"Entry: `{entry:.2f}` | SL: `{sl:.2f}` | TP: `{tp:.2f}`"
                                        )
                                        results.append({
                                            "signal":      "BUY",
                                            "entry":       entry,
                                            "sl":          sl,
                                            "tp":          tp,
                                            "pattern":     _pat,
                                            "reason":      reason,
                                            "order_mode":  "market",
                                            "entry_label": _label,
                                            "sub_pattern": _sub,
                                            "ref_low":     ref_low,
                                            "ref_time":    ref["time"],
                                            "ref_source":  ref["source"],
                                            "rsi_at_ref":  round(ref_rsi, 2),
                                            "rsi_at_rej":  round(s_rsi, 2),
                                            "sweep_bar_time":  int(sweep_bar["time"]),
                                            "sweep_bar_price": s_low,
                                        })

    # ── 3. ตรวจ Engulf (2 confirmation bars + HTF closes RED) ───────
    if want_engulf_swing:
        tf_secs = TF_SECONDS.get(tf, 60)
        htf = _get_s14_htf(tf)
        htf_secs = TF_SECONDS.get(htf, 300)
        
        next_bar_time = int(rates[-1]["time"]) + tf_secs
        if next_bar_time % htf_secs == 0:
            htf_bar_time = next_bar_time - htf_secs
            
            htf_bar = _get_htf_bar(tf, htf_bar_time, htf_rates_lookup)
            if htf_bar:
                ho = float(htf_bar["open"])
                hc = float(htf_bar["close"])
                
                if hc < ho:
                    k = htf_secs // tf_secs
                    start_search = max(0, len(rates) - k - 2)
                    for i in range(start_search, len(rates) - 2):
                        c2_bar = rates[i+2]
                        c2_time = int(c2_bar["time"])
                        if c2_time < htf_bar_time or c2_time >= next_bar_time:
                            continue
                            
                        e_bar = rates[i]
                        c1_bar = rates[i+1]
                        c2_bar = rates[i+2]
                        
                        ref_list = get_ref_low_list(i, use_hhll=True)
                        for ref in ref_list:
                            ref_idx = ref["idx"]
                            ref_low = ref["low"]
                            ref_rsi = _pivot_rsi_buy(rates, rsi_vals, ref_idx)

                            if (ref_rsi is not None or not getattr(config, "S14_RSI_DIV_ENABLED", True)) and i - ref_idx >= 2:
                                # ref_low invalidation: ถ้ามีแท่งระหว่าง ref กับ engulf ปิดต่ำกว่า ref → LL broken
                                if any(float(r["close"]) < ref_low for r in rates[ref_idx + 1:i]):
                                    continue

                                e_low = float(e_bar["low"])
                                e_close = float(e_bar["close"])

                                if e_low < ref_low and e_close < ref_low:
                                    c1_open, c1_close = float(c1_bar["open"]), float(c1_bar["close"])
                                    c2_open, c2_close = float(c2_bar["open"]), float(c2_bar["close"])
                                    if c1_close > c1_open and c2_close > c2_open:
                                        passed_rsi = True
                                        e_rsi = _pivot_rsi_buy(rates, rsi_vals, i)
                                        if getattr(config, "S14_RSI_DIV_ENABLED", True):
                                            _rsi_min_diff = float(getattr(config, "S14_RSI_MIN_DIFF", 1.0))
                                            if e_rsi is None or e_rsi >= 50.0 or (e_rsi - ref_rsi) <= _rsi_min_diff:
                                                passed_rsi = False
                                        if passed_rsi:
                                            
                                            is_sec_htf_triggered = False
                                            sec_htf = _get_next_std_tf(htf)
                                            
                                            if hc >= ref_low:
                                                passed_htf_check = True
                                                sub_pat_suffix = ""
                                            else:
                                                if _is_sec_htf_currently_sweep(rates, tf, sec_htf, ref_low, is_buy=True):
                                                    passed_htf_check = True
                                                    is_sec_htf_triggered = True
                                                    sub_pat_suffix = f"_{sec_htf}"
                                                else:
                                                    passed_htf_check = False
                                            
                                            if passed_htf_check:
                                                entry = round(float(rates[-1]["close"]), 2)
                                                sl = round(min(e_low, float(c1_bar["low"]), float(c2_bar["low"])) - SL_BUFFER(calc_atr(rates, 14)), 2)
                                                if entry > sl:
                                                    tp = _tp_from_window(tp_rates if tp_rates else rates, "BUY", entry, sl)
                                                    if tp is not None:
                                                        sub_pattern = f"engulf{sub_pat_suffix}"
                                                        sec_htf_text = f" | Sec HTF: {sec_htf} Sweep" if is_sec_htf_triggered else ""
                                                        reason = (
                                                            f"[Engulf] Engulf low + 2 Green Confirms + HTF RED ({htf}){sec_htf_text}\n"
                                                            f"ref: `{ref_low:.2f}` ({ref['source']}) | RSI ref: `{ref_rsi:.2f}`\n"
                                                            f"Engulf Bar: L=`{e_low:.2f}` < ref=`{ref_low:.2f}` | C=`{e_close:.2f}` < ref\n"
                                                            f"Confirm 1: O=`{c1_open:.2f}` C=`{c1_close:.2f}` (GREEN)\n"
                                                            f"Confirm 2: O=`{c2_open:.2f}` C=`{c2_close:.2f}` (GREEN)\n"
                                                            f"HTF Bar: O=`{ho:.2f}` C=`{hc:.2f}` (RED)\n"
                                                            f"RSI Div: reject=`{e_rsi:.2f}` > ref=`{ref_rsi:.2f}` (< 50)\n"
                                                            f"Entry: `{entry:.2f}` | SL: `{sl:.2f}` | TP: `{tp:.2f}`"
                                                        )
                                                        res_dict = {
                                                            "signal":      "BUY",
                                                            "entry":       entry,
                                                            "sl":          sl,
                                                            "tp":          tp,
                                                            "pattern":     f"ท่าที่ 14 Sweep RSI 🟢 BUY — Engulf Swing ({sec_htf if is_sec_htf_triggered else htf})",
                                                            "reason":      reason,
                                                            "order_mode":  "market",
                                                            "entry_label": f"BUY MARKET (Engulf Swing {sec_htf if is_sec_htf_triggered else htf})",
                                                            "sub_pattern": sub_pattern,
                                                            "ref_low":     ref_low,
                                                            "ref_time":    ref["time"],
                                                            "ref_source":  ref["source"],
                                                            "rsi_at_ref":  round(ref_rsi, 2),
                                                            "rsi_at_rej":  round(e_rsi, 2),
                                                            "engulf_bar_time": int(e_bar["time"]),
                                                            "engulf_bar_price": e_low,
                                                            "engulf_close": e_close,
                                                            "htf_bar_time": int(htf_bar["time"]),
                                                            "htf_bar_open": ho,
                                                            "htf_bar_close": hc,
                                                            "htf_tf": htf,
                                                        }
                                                        if is_sec_htf_triggered:
                                                            res_dict["sec_htf"] = sec_htf
                                                            res_dict["s14_ref_level"] = ref_low
                                                        results.append(res_dict)
                                                        break

                # --- รูปแบบที่ 2: Direct Engulf (ไม่มี confirm bars, เข้าออเดอร์ทันทีเมื่อจบ HTF) ---
                if want_engulf_swing:
                    e_bar = rates[-1]
                    ref_list_direct = get_ref_low_list(len(rates) - 1, use_hhll=True)
                    for ref in ref_list_direct:
                        ref_idx = ref["idx"]
                        ref_low = ref["low"]
                        ref_rsi = _pivot_rsi_buy(rates, rsi_vals, ref_idx)
                        
                        if (ref_rsi is not None or not getattr(config, "S14_RSI_DIV_ENABLED", True)) and (len(rates) - 1) - ref_idx >= 2:
                            # ref_low invalidation: ถ้ามีแท่งระหว่าง ref กับ engulf direct ปิดต่ำกว่า ref → LL broken
                            if any(float(r["close"]) < ref_low for r in rates[ref_idx + 1:len(rates) - 1]):
                                continue

                            e_low = float(e_bar["low"])
                            e_close = float(e_bar["close"])

                            if e_low < ref_low and e_close < ref_low:
                                passed_rsi = True
                                e_rsi = _pivot_rsi_buy(rates, rsi_vals, len(rates) - 1)
                                if getattr(config, "S14_RSI_DIV_ENABLED", True):
                                    _rsi_min_diff = float(getattr(config, "S14_RSI_MIN_DIFF", 1.0))
                                    if e_rsi is None or e_rsi >= 50.0 or (e_rsi - ref_rsi) <= _rsi_min_diff:
                                        passed_rsi = False
                                if passed_rsi:
                                    
                                    sec_htf = _get_next_std_tf(htf)
                                    if hc < ho and hc < ref_low:
                                        if _is_sec_htf_currently_sweep(rates, tf, sec_htf, ref_low, is_buy=True):
                                            entry = round(e_close, 2)
                                            sl = round(e_low - SL_BUFFER(calc_atr(rates, 14)), 2)
                                            if entry > sl:
                                                tp = _tp_from_window(tp_rates if tp_rates else rates, "BUY", entry, sl)
                                                if tp is not None:
                                                    sub_pattern = f"engulf_{sec_htf}"
                                                    reason = (
                                                        f"[Engulf Direct] Engulf low (no confirm bars) + HTF RED ({htf}) | Sec HTF: {sec_htf} Sweep\n"
                                                        f"ref: `{ref_low:.2f}` ({ref['source']}) | RSI ref: `{ref_rsi:.2f}`\n"
                                                        f"Engulf Bar: L=`{e_low:.2f}` < ref=`{ref_low:.2f}` | C=`{e_close:.2f}` < ref\n"
                                                        f"HTF Bar: O=`{ho:.2f}` C=`{hc:.2f}` (RED)\n"
                                                        f"RSI Div: reject=`{e_rsi:.2f}` > ref=`{ref_rsi:.2f}` (< 50)\n"
                                                        f"Entry: `{entry:.2f}` | SL: `{sl:.2f}` | TP: `{tp:.2f}`"
                                                    )
                                                    results.append({
                                                        "signal":      "BUY",
                                                        "entry":       entry,
                                                        "sl":          sl,
                                                        "tp":          tp,
                                                        "pattern":     f"ท่าที่ 14 Sweep RSI 🟢 BUY — Engulf Swing ({sec_htf})",
                                                        "reason":      reason,
                                                        "order_mode":  "market",
                                                        "entry_label": f"BUY MARKET (Engulf Swing {sec_htf})",
                                                        "sub_pattern": sub_pattern,
                                                        "ref_low":     ref_low,
                                                        "ref_time":    ref["time"],
                                                        "ref_source":  ref["source"],
                                                        "rsi_at_ref":  round(ref_rsi, 2),
                                                        "rsi_at_rej":  round(e_rsi, 2),
                                                        "sec_htf":     sec_htf,
                                                        "s14_ref_level": ref_low,
                                                        "engulf_bar_time": int(e_bar["time"]),
                                                        "engulf_bar_price": e_low,
                                                        "engulf_close": e_close,
                                                        "htf_bar_time": int(htf_bar["time"]),
                                                        "htf_bar_open": ho,
                                                        "htf_bar_close": hc,
                                                        "htf_tf": htf,
                                                    })
                                                    break

    return results


# ─────────────────────────────────────────────────────────────────────────────
# SELL — Engulf & Sweep
# ─────────────────────────────────────────────────────────────────────────────

def _build_sell_results(rates, rsi_vals, tf: str, tp_rates=None, htf_rates_lookup: dict = None) -> list:
    """
    ตรวจ S14 SELL ทั้ง Engulf และ Sweep patterns โดยใช้ confirmation bars:
    - Sweep: rates[-2] is sweep high, rates[-1] is RED confirm bar. Enter on next bar open.
    - Engulf: rates[i] is engulf high, rates[i+1], rates[i+2] are RED confirm bars, and HTF bar closes GREEN (or secondary HTF is sweep). Enter on next HTF bar.
    """
    want_swing        = getattr(config, "S14_SWEEP_SWING",  True)
    want_engulf_swing = getattr(config, "S14_ENGULF_SWING", True)
    want_sweep        = getattr(config, "S14_SWEEP_RETURN", True)
    if not want_swing and not want_engulf_swing and not want_sweep:
        return []

    if len(rates) < 6:
        return []

    results = []

    def get_ref_high_list(setup_idx, use_hhll=False):
        candidates = []
        if not use_hhll:
            local_high_idxs = _find_local_highs(rates)
            if local_high_idxs:
                valid_highs = [idx for idx in local_high_idxs if setup_idx - idx >= 2]
                if valid_highs:
                    lh_idx = max(valid_highs)
                    candidates.append({
                        "idx":    lh_idx,
                        "time":   int(rates[lh_idx]["time"]),
                        "high":   float(rates[lh_idx]["high"]),
                        "source": "local_high",
                    })
        else:
            try:
                import hhll_swing
                data = hhll_swing.get_hhll_data(tf)
                pts = []
                for k in ["hh", "lh", "prev_hh", "prev_lh"]:
                    pt = data.get(k)
                    if pt:
                        pts.append(pt)
                for pt in pts:
                    pt_time = int(pt["time"])
                    for idx in range(len(rates)):
                        if idx < setup_idx - 1 and int(rates[idx]["time"]) == pt_time:
                            candidates.append({
                                "idx":    idx,
                                "time":   pt_time,
                                "high":   float(pt["price"]),
                                "source": pt.get("label", "hhll_sh"),
                            })
                            break
            except Exception:
                pass
        if not candidates:
            return []
        newest = max(candidates, key=lambda c: c["time"])
        active_refs = [newest]
        if newest["source"] != "HH":
            hh_cands = [c for c in candidates if c["source"] == "HH"]
            if hh_cands:
                latest_hh = max(hh_cands, key=lambda c: c["time"])
                if latest_hh["time"] != newest["time"]:
                    active_refs.append(latest_hh)
        return active_refs

    # ── 2. ตรวจ Sweep (รอ confirm bar แดงหลัง sweep จบ) ─────────────────────
    # want_swing  = HHLL swing ref  → SSS/BSS
    # want_sweep  = local_high ref  → SRS/BRS
    if (want_swing or want_sweep) and len(rates) >= 3:
        confirm_idx = len(rates) - 1
        sweep_idx   = len(rates) - 2
        confirm_bar = rates[confirm_idx]
        sweep_bar   = rates[sweep_idx]
        co, cc = float(confirm_bar["open"]), float(confirm_bar["close"])

        if cc < co:  # confirm bar ต้องแดง
            for _use_hhll, _active, _pat, _label, _sub in [
                (True,  want_swing,  "ท่าที่ 14 Sweep RSI 🔴 SELL — Sweep Swing",    "SELL MARKET (Sweep Swing)",    "swing"),
                (False, want_sweep,  "ท่าที่ 14 Sweep RSI 🔴 SELL — Sweep กลับตัว", "SELL MARKET (Sweep กลับตัว)", "sweep"),
            ]:
                if not _active:
                    continue
                ref_list = get_ref_high_list(sweep_idx, use_hhll=_use_hhll)
                for ref in ref_list:
                    ref_idx  = ref["idx"]
                    ref_high = ref["high"]
                    ref_rsi  = _pivot_rsi_sell(rates, rsi_vals, ref_idx)

                    if (ref_rsi is not None or not getattr(config, "S14_RSI_DIV_ENABLED", True)) and sweep_idx - ref_idx >= 2:
                        # ref_high invalidation: ถ้ามีแท่งระหว่าง ref กับ sweep ปิดสูงกว่า ref → LH broken
                        if any(float(r["close"]) > ref_high for r in rates[ref_idx + 1:sweep_idx]):
                            continue

                        s_high  = float(sweep_bar["high"])
                        s_open  = float(sweep_bar["open"])
                        s_close = float(sweep_bar["close"])

                        if s_high > ref_high and s_open < ref_high and s_close < ref_high:
                            passed_rsi = True
                            s_rsi = _pivot_rsi_sell(rates, rsi_vals, sweep_idx)
                            if getattr(config, "S14_RSI_DIV_ENABLED", True):
                                _rsi_min_diff = float(getattr(config, "S14_RSI_MIN_DIFF", 1.0))
                                if s_rsi is None or s_rsi <= 50.0 or (ref_rsi - s_rsi) <= _rsi_min_diff:
                                    passed_rsi = False
                            if passed_rsi:
                                entry = round(cc, 2)
                                sl    = round(s_high + SL_BUFFER(calc_atr(rates, 14)), 2)
                                if entry < sl:
                                    tp = _tp_from_window(tp_rates if tp_rates else rates, "SELL", entry, sl)
                                    if tp is not None:
                                        reason = (
                                            f"[Sweep] Sweep high + confirm RED\n"
                                            f"ref: `{ref_high:.2f}` ({ref['source']}) | RSI ref: `{ref_rsi:.2f}`\n"
                                            f"Sweep Bar: H=`{s_high:.2f}` > ref=`{ref_high:.2f}` | C=`{s_close:.2f}` <= ref\n"
                                            f"Confirm: C=`{cc:.2f}` (RED)\n"
                                            f"RSI Div: reject=`{s_rsi:.2f}` < ref=`{ref_rsi:.2f}` (> 50)\n"
                                            f"Entry: `{entry:.2f}` | SL: `{sl:.2f}` | TP: `{tp:.2f}`"
                                        )
                                        results.append({
                                            "signal":      "SELL",
                                            "entry":       entry,
                                            "sl":          sl,
                                            "tp":          tp,
                                            "pattern":     _pat,
                                            "reason":      reason,
                                            "order_mode":  "market",
                                            "entry_label": _label,
                                            "sub_pattern": _sub,
                                            "ref_high":    ref_high,
                                            "ref_time":    ref["time"],
                                            "ref_source":  ref["source"],
                                            "rsi_at_ref":  round(ref_rsi, 2),
                                            "rsi_at_rej":  round(s_rsi, 2),
                                            "sweep_bar_time":  int(sweep_bar["time"]),
                                            "sweep_bar_price": s_high,
                                        })

    # ── 3. ตรวจ Engulf (2 confirmation bars + HTF closes GREEN) ──────
    if want_engulf_swing:
        tf_secs = TF_SECONDS.get(tf, 60)
        htf = _get_s14_htf(tf)
        htf_secs = TF_SECONDS.get(htf, 300)

        next_bar_time = int(rates[-1]["time"]) + tf_secs
        if next_bar_time % htf_secs == 0:
            htf_bar_time = next_bar_time - htf_secs

            htf_bar = _get_htf_bar(tf, htf_bar_time, htf_rates_lookup)
            if htf_bar:
                ho = float(htf_bar["open"])
                hc = float(htf_bar["close"])

                if hc > ho:
                    k = htf_secs // tf_secs
                    start_search = max(0, len(rates) - k - 2)
                    for i in range(start_search, len(rates) - 2):
                        e_bar = rates[i]
                        c1_bar = rates[i+1]
                        c2_bar = rates[i+2]

                        c2_time = int(c2_bar["time"])
                        if c2_time < htf_bar_time or c2_time >= next_bar_time:
                            continue

                        ref_list = get_ref_high_list(i, use_hhll=True)
                        for ref in ref_list:
                            ref_idx = ref["idx"]
                            ref_high = ref["high"]
                            ref_rsi = _pivot_rsi_sell(rates, rsi_vals, ref_idx)

                            if (ref_rsi is not None or not getattr(config, "S14_RSI_DIV_ENABLED", True)) and i - ref_idx >= 2:
                                # ref_high invalidation: ถ้ามีแท่งระหว่าง ref กับ engulf ปิดสูงกว่า ref → LH broken
                                if any(float(r["close"]) > ref_high for r in rates[ref_idx + 1:i]):
                                    continue

                                e_high = float(e_bar["high"])
                                e_close = float(e_bar["close"])

                                if e_high > ref_high and e_close > ref_high:
                                    c1_open, c1_close = float(c1_bar["open"]), float(c1_bar["close"])
                                    c2_open, c2_close = float(c2_bar["open"]), float(c2_bar["close"])
                                    if c1_close < c1_open and c2_close < c2_open:
                                        passed_rsi = True
                                        e_rsi = _pivot_rsi_sell(rates, rsi_vals, i)
                                        if getattr(config, "S14_RSI_DIV_ENABLED", True):
                                            _rsi_min_diff = float(getattr(config, "S14_RSI_MIN_DIFF", 1.0))
                                            if e_rsi is None or e_rsi <= 50.0 or (ref_rsi - e_rsi) <= _rsi_min_diff:
                                                passed_rsi = False
                                        if passed_rsi:
                                            
                                            is_sec_htf_triggered = False
                                            sec_htf = _get_next_std_tf(htf)

                                            if hc <= ref_high:
                                                passed_htf_check = True
                                                sub_pat_suffix = ""
                                            else:
                                                if _is_sec_htf_currently_sweep(rates, tf, sec_htf, ref_high, is_buy=False):
                                                    passed_htf_check = True
                                                    is_sec_htf_triggered = True
                                                    sub_pat_suffix = f"_{sec_htf}"
                                                else:
                                                    passed_htf_check = False

                                            if passed_htf_check:
                                                entry = round(float(rates[-1]["close"]), 2)
                                                sl = round(max(e_high, float(c1_bar["high"]), float(c2_bar["high"])) + SL_BUFFER(calc_atr(rates, 14)), 2)
                                                if entry < sl:
                                                    tp = _tp_from_window(tp_rates if tp_rates else rates, "SELL", entry, sl)
                                                    if tp is not None:
                                                        sub_pattern = f"engulf{sub_pat_suffix}"
                                                        sec_htf_text = f" | Sec HTF: {sec_htf} Sweep" if is_sec_htf_triggered else ""
                                                        reason = (
                                                            f"[Engulf] Engulf high + 2 Red Confirms + HTF GREEN ({htf}){sec_htf_text}\n"
                                                            f"ref: `{ref_high:.2f}` ({ref['source']}) | RSI ref: `{ref_rsi:.2f}`\n"
                                                            f"Engulf Bar: H=`{e_high:.2f}` > ref=`{ref_high:.2f}` | C=`{e_close:.2f}` > ref\n"
                                                            f"Confirm 1: O=`{c1_open:.2f}` C=`{c1_close:.2f}` (RED)\n"
                                                            f"Confirm 2: O=`{c2_open:.2f}` C=`{c2_close:.2f}` (RED)\n"
                                                            f"HTF Bar: O=`{ho:.2f}` C=`{hc:.2f}` (GREEN)\n"
                                                            f"RSI Div: reject=`{e_rsi:.2f}` < ref=`{ref_rsi:.2f}` (> 50)\n"
                                                            f"Entry: `{entry:.2f}` | SL: `{sl:.2f}` | TP: `{tp:.2f}`"
                                                        )
                                                        res_dict = {
                                                            "signal":      "SELL",
                                                            "entry":       entry,
                                                            "sl":          sl,
                                                            "tp":          tp,
                                                            "pattern":     f"ท่าที่ 14 Sweep RSI 🔴 SELL — Engulf Swing ({sec_htf if is_sec_htf_triggered else htf})",
                                                            "reason":      reason,
                                                            "order_mode":  "market",
                                                            "entry_label": f"SELL MARKET (Engulf Swing {sec_htf if is_sec_htf_triggered else htf})",
                                                            "sub_pattern": sub_pattern,
                                                            "ref_high":    ref_high,
                                                            "ref_time":    ref["time"],
                                                            "ref_source":  ref["source"],
                                                            "rsi_at_ref":  round(ref_rsi, 2),
                                                            "rsi_at_rej":  round(e_rsi, 2),
                                                            "engulf_bar_time": int(e_bar["time"]),
                                                            "engulf_bar_price": e_high,
                                                            "engulf_close": e_close,
                                                            "htf_bar_time": int(htf_bar["time"]),
                                                            "htf_bar_open": ho,
                                                            "htf_bar_close": hc,
                                                            "htf_tf": htf,
                                                        }
                                                        if is_sec_htf_triggered:
                                                            res_dict["sec_htf"] = sec_htf
                                                            res_dict["s14_ref_level"] = ref_high
                                                        results.append(res_dict)
                                                        break

                # --- รูปแบบที่ 2: Direct Engulf (ไม่มี confirm bars, เข้าออเดอร์ทันทีเมื่อจบ HTF) ---
                if want_engulf_swing:
                    e_bar = rates[-1]
                    ref_list_direct = get_ref_high_list(len(rates) - 1, use_hhll=True)
                    for ref in ref_list_direct:
                        ref_idx = ref["idx"]
                        ref_high = ref["high"]
                        ref_rsi = _pivot_rsi_sell(rates, rsi_vals, ref_idx)
                        
                        if (ref_rsi is not None or not getattr(config, "S14_RSI_DIV_ENABLED", True)) and (len(rates) - 1) - ref_idx >= 2:
                            # ref_high invalidation: ถ้ามีแท่งระหว่าง ref กับ engulf direct ปิดสูงกว่า ref → LH broken
                            if any(float(r["close"]) > ref_high for r in rates[ref_idx + 1:len(rates) - 1]):
                                continue

                            e_high = float(e_bar["high"])
                            e_close = float(e_bar["close"])

                            if e_high > ref_high and e_close > ref_high:
                                passed_rsi = True
                                e_rsi = _pivot_rsi_sell(rates, rsi_vals, len(rates) - 1)
                                if getattr(config, "S14_RSI_DIV_ENABLED", True):
                                    _rsi_min_diff = float(getattr(config, "S14_RSI_MIN_DIFF", 1.0))
                                    if e_rsi is None or e_rsi <= 50.0 or (ref_rsi - e_rsi) <= _rsi_min_diff:
                                        passed_rsi = False
                                if passed_rsi:
                                    
                                    sec_htf = _get_next_std_tf(htf)
                                    if hc > ho and hc > ref_high:
                                        if _is_sec_htf_currently_sweep(rates, tf, sec_htf, ref_high, is_buy=False):
                                            entry = round(e_close, 2)
                                            sl = round(e_high + SL_BUFFER(calc_atr(rates, 14)), 2)
                                            if entry < sl:
                                                tp = _tp_from_window(tp_rates if tp_rates else rates, "SELL", entry, sl)
                                                if tp is not None:
                                                    sub_pattern = f"engulf_{sec_htf}"
                                                    reason = (
                                                        f"[Engulf Direct] Engulf high (no confirm bars) + HTF GREEN ({htf}) | Sec HTF: {sec_htf} Sweep\n"
                                                        f"ref: `{ref_high:.2f}` ({ref['source']}) | RSI ref: `{ref_rsi:.2f}`\n"
                                                        f"Engulf Bar: H=`{e_high:.2f}` > ref=`{ref_high:.2f}` | C=`{e_close:.2f}` > ref\n"
                                                        f"HTF Bar: O=`{ho:.2f}` C=`{hc:.2f}` (GREEN)\n"
                                                        f"RSI Div: reject=`{e_rsi:.2f}` < ref=`{ref_rsi:.2f}` (> 50)\n"
                                                        f"Entry: `{entry:.2f}` | SL: `{sl:.2f}` | TP: `{tp:.2f}`"
                                                    )
                                                    results.append({
                                                        "signal":      "SELL",
                                                        "entry":       entry,
                                                        "sl":          sl,
                                                        "tp":          tp,
                                                        "pattern":     f"ท่าที่ 14 Sweep RSI 🔴 SELL — Engulf Swing ({sec_htf})",
                                                        "reason":      reason,
                                                        "order_mode":  "market",
                                                        "entry_label": f"SELL MARKET (Engulf Swing {sec_htf})",
                                                        "sub_pattern": sub_pattern,
                                                        "ref_high":    ref_high,
                                                        "ref_time":    ref["time"],
                                                        "ref_source":  ref["source"],
                                                        "rsi_at_ref":  round(ref_rsi, 2),
                                                        "rsi_at_rej":  round(e_rsi, 2),
                                                        "sec_htf":     sec_htf,
                                                        "s14_ref_level": ref_high,
                                                        "engulf_bar_time": int(e_bar["time"]),
                                                        "engulf_bar_price": e_high,
                                                        "engulf_close": e_close,
                                                        "htf_bar_time": int(htf_bar["time"]),
                                                        "htf_bar_open": ho,
                                                        "htf_bar_close": hc,
                                                        "htf_tf": htf,
                                                    })
                                                    break

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def _dedupe_s14_orders(orders: list) -> list:
    unique = []
    seen = set()
    for order in orders:
        key = (
            str(order.get("signal", "")).upper(),
            str(order.get("order_mode", "market")),
            round(float(order.get("entry", 0.0) or 0.0), 2),
            round(float(order.get("tp", 0.0) or 0.0), 2),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(order)
    return unique


def strategy_14(rates, tf: str = "", htf_rates_lookup: dict = None):
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

    # ── Block SIDEWAY trend (ข้อมูลจริง 06-2026: 0% WR, -$58.20 จาก 4 orders) ──
    if getattr(config, "S14_BLOCK_SIDEWAY", True) and tf:
        try:
            import hhll_swing as _hs
            _s14_trend = _hs.get_trend_from_structure(tf)
            if _s14_trend.get("trend", "") == "SIDEWAY":
                return {"signal": "WAIT", "reason": f"S14: SIDEWAY trend → block (S14_BLOCK_SIDEWAY)"}
        except Exception:
            pass

    full_rates = list(rates)                                    # ทั้งหมดสำหรับ TP (HHLL)
    window     = list(rates[-(lookback + period + 5):])        # 69 bars สำหรับ RSI/signal
    rsi_vals   = _calc_rsi_values(window, period=period, applied_price=applied)

    all_results = []
    all_results.extend(_build_buy_results(window, rsi_vals, tf, tp_rates=full_rates, htf_rates_lookup=htf_rates_lookup))
    all_results.extend(_build_sell_results(window, rsi_vals, tf, tp_rates=full_rates, htf_rates_lookup=htf_rates_lookup))
    all_results = _dedupe_s14_orders(all_results)

    if not all_results:
        return {"signal": "WAIT", "reason": "S14: ไม่พบ Sweep RSI setup"}

    if len(all_results) == 1:
        return all_results[0]

    # multi (เช่น BUY Engulf + BUY Sweep บน bar เดียวกัน — ต้องเกิดพร้อมกัน)
    return {"signal": "MULTI", "orders": all_results}
