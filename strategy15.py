"""
strategy15.py — S15 Volume Profile POC + Absorption
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Win Rate อ้างอิง: 85-90% (POC Defense + Absorption)

แนวคิด (Volume Profile + Institutional Absorption):
  1. คำนวณ Volume Profile จาก S15_LOOKBACK bars ล่าสุด (proxy: tick_volume)
       POC = price level ที่มี volume มากที่สุด → "แม่เหล็กราคา"
       VAH = Value Area High (ขอบบน 70% volume zone)
       VAL = Value Area Low  (ขอบล่าง 70% volume zone)
  2. ตรวจ Absorption pattern ที่ POC/VAL/VAH:
       Pattern A — Long wick sweep: ไส้ยาว ≥ S15_ABSORPTION_WICK_PCT × range
                   แต่ปิด (close) กลับเข้าโซน → สัญญาณดูดซับแรงขาย/ซื้อ
       Pattern B — 2-bar reversal: prev red → cur green (BUY)
                                    prev green → cur red (SELL)
  3. Entry: LIMIT ที่ POC หรือ VAL (BUY) / POC หรือ VAH (SELL)
  4. SL: ต่ำกว่า low ของ absorption bar (BUY) / สูงกว่า high (SELL)
  5. TP: VAH/swing high (BUY) | VAL/swing low (SELL), RR ≥ S15_MIN_RR

Order type: LIMIT
Bypass: ไม่ bypass trend filter (ผ่านระบบ filter ปกติ)
"""

import config
from config import SL_BUFFER
from mt5_utils import calc_atr, TF_SECONDS_MAP

# Per-level cooldown state: {(tf, side, level_bucket): last_bar_time}
# กันยิง LIMIT ซ้ำที่ POC/VAL/VAH เดิม ทุกแท่ง (entry นิ่งแต่ SL เปลี่ยน → dedup เดิมไม่จับ)
_s15_last_fire: dict = {}


def _ema(values, period):
    """EMA แบบ manual (ไม่พึ่ง numpy/talib)"""
    if not values or period <= 0:
        return None
    k = 2.0 / (period + 1.0)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1.0 - k)
    return e


def _level_on_cooldown(tf, side, level, bar_time, cooldown_bars, tf_secs):
    """True ถ้า level นี้เพิ่งยิงไปภายใน cooldown_bars แท่ง"""
    key = (tf, side, round(float(level), 1))
    last = _s15_last_fire.get(key, 0)
    if bar_time - last < cooldown_bars * tf_secs:
        return True
    return False


def _mark_fired(tf, side, level, bar_time):
    _s15_last_fire[(tf, side, round(float(level), 1))] = bar_time


# ─────────────────────────────────────────────────────────────────────────────
# Volume Profile Calculation
# ─────────────────────────────────────────────────────────────────────────────

def _bar_volume(bar):
    """ดึง volume ของ 1 แท่งแบบปลอดภัย
    rates เป็น numpy structured array → ใช้ index access (bar["..."]) เท่านั้น
    ห้ามใช้ bar.get() เพราะ numpy.void ไม่มี .get() (AGENTS.md numpy rates check)
    fallback: tick_volume → real_volume → 1.0
    """
    for field in ("tick_volume", "real_volume"):
        try:
            v = float(bar[field])
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        if v > 0:
            return v
    return 1.0


def _calc_vp(rates, lookback):
    """
    คำนวณ POC, VAH, VAL จาก tick_volume ของ lookback bars ล่าสุด
    (ไม่รวมแท่งปัจจุบัน rates[-1])

    bucket_size = ATR/10 เพื่อ auto-scale ตาม instrument (XAU/BTC)
    Returns: {"poc": float, "vah": float, "val": float} หรือ None
    """
    n = len(rates)
    if n < lookback + 2:
        return None
    window = rates[-(lookback + 1):-1]
    if len(window) < 5:
        return None

    atr = calc_atr(rates)
    if not atr or atr <= 0:
        atr = max(float(rates[-2]["high"]) - float(rates[-2]["low"]), 0.01) * 5
    bucket_size = max(atr / 10.0, 0.001)

    price_vol: dict = {}
    total_vol = 0.0
    for bar in window:
        mid = (float(bar["high"]) + float(bar["low"])) / 2.0
        bucket = round(round(mid / bucket_size) * bucket_size, 5)
        vol = _bar_volume(bar)
        price_vol[bucket] = price_vol.get(bucket, 0.0) + vol
        total_vol += vol

    if not price_vol or total_vol == 0:
        return None

    poc = max(price_vol, key=lambda p: price_vol[p])
    sorted_prices = sorted(price_vol)
    try:
        poc_idx = sorted_prices.index(poc)
    except ValueError:
        return None

    va_target = total_vol * float(getattr(config, "S15_VAL_VAH_PCT", 0.70))
    va_vol = price_vol[poc]
    lo_idx = poc_idx
    hi_idx = poc_idx

    while va_vol < va_target:
        lo_vol = price_vol[sorted_prices[lo_idx - 1]] if lo_idx > 0 else 0.0
        hi_vol = price_vol[sorted_prices[hi_idx + 1]] if hi_idx < len(sorted_prices) - 1 else 0.0
        if lo_vol == 0.0 and hi_vol == 0.0:
            break
        if lo_vol >= hi_vol and lo_idx > 0:
            lo_idx -= 1
            va_vol += lo_vol
        elif hi_idx < len(sorted_prices) - 1:
            hi_idx += 1
            va_vol += hi_vol
        else:
            break

    return {
        "poc": poc,
        "val": sorted_prices[lo_idx],
        "vah": sorted_prices[hi_idx],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Absorption Pattern Detection
# ─────────────────────────────────────────────────────────────────────────────

def _near(a, b, tol):
    return abs(a - b) <= tol


def _absorption_buy(rates, ref_price, tolerance, strict=False):
    """
    ตรวจ absorption ฝั่ง BUY ที่ ref_price (POC หรือ VAL)
    True = มีแรงซื้อดูดแรงขายที่ level นี้

    Pattern A: lower wick ≥ wick_pct × range + ราคาแตะ ref zone (อ่อน)
    Pattern B: prev red → cur green close ≥ ref_price (2-bar demand reversal — แข็ง)

    strict=True → ใช้ Pattern B อย่างเดียว (reversal confirmation) + ต้องมี wick ด้วย
    """
    if len(rates) < 2:
        return False
    cur  = rates[-1]
    prev = rates[-2]
    c_o   = float(cur["open"])
    c_c   = float(cur["close"])
    c_h   = float(cur["high"])
    c_l   = float(cur["low"])
    c_rng = c_h - c_l
    if c_rng <= 0:
        return False

    wick_pct    = float(getattr(config, "S15_ABSORPTION_WICK_PCT", 0.30))
    lower_wick  = min(c_o, c_c) - c_l
    in_zone     = _near(c_l, ref_price, tolerance) or (c_l <= ref_price <= c_h)

    # Pattern B (2-bar reversal): prev red → cur green ปิดเหนือ ref
    p_o = float(prev["open"])
    p_c = float(prev["close"])
    pattern_b = (p_c < p_o and c_c > c_o
                 and _near(c_l, ref_price, tolerance * 2)
                 and c_c >= ref_price)

    if strict:
        # ต้อง reversal จริง + มี rejection wick ≥ wick_pct (กรอง setup อ่อน)
        return bool(pattern_b and lower_wick >= wick_pct * c_rng)

    # Pattern A (อ่อน): wick + in zone
    if in_zone and lower_wick >= wick_pct * c_rng:
        return True
    return bool(pattern_b)


def _absorption_sell(rates, ref_price, tolerance, strict=False):
    """
    ตรวจ absorption ฝั่ง SELL ที่ ref_price (POC หรือ VAH)
    True = มีแรงขายดูดแรงซื้อที่ level นี้

    Pattern A: upper wick ≥ wick_pct × range + ราคาแตะ ref zone (อ่อน)
    Pattern B: prev green → cur red close ≤ ref_price (2-bar supply reversal — แข็ง)

    strict=True → ใช้ Pattern B อย่างเดียว + ต้องมี wick ด้วย
    """
    if len(rates) < 2:
        return False
    cur  = rates[-1]
    prev = rates[-2]
    c_o   = float(cur["open"])
    c_c   = float(cur["close"])
    c_h   = float(cur["high"])
    c_l   = float(cur["low"])
    c_rng = c_h - c_l
    if c_rng <= 0:
        return False

    wick_pct    = float(getattr(config, "S15_ABSORPTION_WICK_PCT", 0.30))
    upper_wick  = c_h - max(c_o, c_c)
    in_zone     = _near(c_h, ref_price, tolerance) or (c_l <= ref_price <= c_h)

    p_o = float(prev["open"])
    p_c = float(prev["close"])
    pattern_b = (p_c > p_o and c_c < c_o
                 and _near(c_h, ref_price, tolerance * 2)
                 and c_c <= ref_price)

    if strict:
        return bool(pattern_b and upper_wick >= wick_pct * c_rng)

    if in_zone and upper_wick >= wick_pct * c_rng:
        return True
    return bool(pattern_b)


# ─────────────────────────────────────────────────────────────────────────────
# TP Calculation
# ─────────────────────────────────────────────────────────────────────────────

def _tp_buy(rates, entry, sl, vah):
    risk    = entry - sl
    if risk <= 0:
        return None
    min_rr  = float(getattr(config, "S15_MIN_RR", 1.0))
    min_tp  = entry + risk * min_rr
    if vah > min_tp:
        return round(vah, 2)
    highs = [float(b["high"]) for b in rates[-31:-1] if float(b["high"]) > min_tp]
    if highs:
        return round(min(highs), 2)
    return round(min_tp, 2)


def _tp_sell(rates, entry, sl, val):
    risk    = sl - entry
    if risk <= 0:
        return None
    min_rr  = float(getattr(config, "S15_MIN_RR", 1.0))
    min_tp  = entry - risk * min_rr
    if val < min_tp:
        return round(val, 2)
    lows = [float(b["low"]) for b in rates[-31:-1] if float(b["low"]) < min_tp]
    if lows:
        return round(max(lows), 2)
    return round(min_tp, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Main Strategy Entry
# ─────────────────────────────────────────────────────────────────────────────

def strategy_15(rates, tf: str = ""):
    """
    S15 Volume Profile POC + Absorption

    Returns
    -------
    {"signal": "BUY"|"SELL"|"MULTI"|"WAIT", "entry", "sl", "tp",
     "pattern", "reason", "order_mode": "limit", ...}
    """
    lookback       = int(getattr(config,   "S15_LOOKBACK",       100))
    use_val_vah    = bool(getattr(config,  "S15_USE_VAL_VAH",    True))
    zone_atr_mult  = float(getattr(config, "S15_ZONE_ATR_MULT",  0.5))
    min_bars       = lookback + 5

    if rates is None or len(rates) < min_bars:
        n = len(rates) if rates is not None else 0
        return {"signal": "WAIT", "reason": f"S15: ข้อมูลไม่พอ (ต้องการ {min_bars} มี {n})"}

    vp = _calc_vp(rates, lookback)
    if vp is None:
        return {"signal": "WAIT", "reason": "S15: คำนวณ Volume Profile ไม่ได้"}

    poc = vp["poc"]
    val = vp["val"]
    vah = vp["vah"]

    atr = calc_atr(rates)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S15: คำนวณ ATR ไม่ได้"}

    sl_buf    = SL_BUFFER(atr)
    tolerance = atr * zone_atr_mult

    cur       = rates[-1]
    cur_low   = float(cur["low"])
    cur_high  = float(cur["high"])
    cur_close = float(cur["close"])
    bar_time  = int(cur["time"])
    results   = []

    # ── Trend filter (กัน mean-reversion สวนเทรนด์) ────────────────────
    # absorption เป็น mean-reversion → ในเทรนด์แรง ฝั่งสวนเทรนด์ขาดทุนหนัก
    # (ข้อมูลจริง 02-03/06: BUY สวนเทรนด์ลง = -177, SELL ตามเทรนด์ = +22)
    # กติกา: BUY เฉพาะตอน close ≥ EMA (ขาขึ้น/นิ่ง), SELL เฉพาะ close ≤ EMA
    allow_buy = allow_sell = True
    if bool(getattr(config, "S15_TREND_FILTER", True)):
        ema_period = int(getattr(config, "S15_TREND_EMA", 50))
        closes = [float(b["close"]) for b in rates[-(ema_period * 3):]]
        ema = _ema(closes, ema_period)
        if ema is not None:
            band = atr * float(getattr(config, "S15_TREND_NEUTRAL_ATR", 0.1))
            if cur_close < ema - band:
                allow_buy = False    # ขาลง → ห้าม BUY สวน
            elif cur_close > ema + band:
                allow_sell = False   # ขาขึ้น → ห้าม SELL สวน

    cooldown_bars = int(getattr(config, "S15_LEVEL_COOLDOWN_BARS", 15))
    tf_secs = int(TF_SECONDS_MAP.get(tf, 60)) if tf else 60

    # strict mode: เข้าเฉพาะ value-area edge (VAL-BUY / VAH-SELL) ที่มี 2-bar reversal
    # POC เป็น magnet ก้ำกึ่ง (ทั้ง BUY/SELL ยิงที่เดียวกัน) → ข้ามใน strict
    strict = bool(getattr(config, "S15_STRICT_MODE", True))

    vp_info = f"POC={poc:.2f} | VAL={val:.2f} | VAH={vah:.2f} | ATR={atr:.2f}"

    # ── BUY at POC ──────────────────────────────────────────────────
    # BUY LIMIT: entry ต้องต่ำกว่า close (รอราคาย้อนลงมาแตะ level) มิฉะนั้น open_order จะ skip
    if not strict and allow_buy and not _level_on_cooldown(tf, "BUY", poc, bar_time, cooldown_bars, tf_secs) \
            and _absorption_buy(rates, poc, tolerance, strict=strict):
        entry = round(poc, 2)
        sl    = round(cur_low - sl_buf, 2)
        tp    = _tp_buy(rates, entry, sl, vah)
        if tp and tp > entry > sl and entry < cur_close:
            _mark_fired(tf, "BUY", poc, bar_time)
            results.append({
                "signal":      "BUY",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 15 VP POC 🟢 BUY — Absorption",
                "reason":      f"{vp_info}\nAbsorption ที่ POC",
                "order_mode":  "limit",
                "entry_label": "BUY LIMIT (POC Absorption)",
                "vp_poc": poc, "vp_val": val, "vp_vah": vah,
            })

    # ── BUY at VAL ──────────────────────────────────────────────────
    if allow_buy and use_val_vah and val != poc \
            and not _level_on_cooldown(tf, "BUY", val, bar_time, cooldown_bars, tf_secs) \
            and _absorption_buy(rates, val, tolerance, strict=strict):
        entry = round(val, 2)
        sl    = round(cur_low - sl_buf, 2)
        tp    = _tp_buy(rates, entry, sl, poc)
        if tp and tp > entry > sl and entry < cur_close:
            _mark_fired(tf, "BUY", val, bar_time)
            results.append({
                "signal":      "BUY",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 15 VP VAL 🟢 BUY — Absorption",
                "reason":      f"{vp_info}\nAbsorption ที่ VAL",
                "order_mode":  "limit",
                "entry_label": "BUY LIMIT (VAL Absorption)",
                "vp_poc": poc, "vp_val": val, "vp_vah": vah,
            })

    # ── SELL at POC ─────────────────────────────────────────────────
    # SELL LIMIT: entry ต้องสูงกว่า close (รอราคาย้อนขึ้นมาแตะ level) มิฉะนั้น open_order จะ skip
    if not strict and allow_sell and not _level_on_cooldown(tf, "SELL", poc, bar_time, cooldown_bars, tf_secs) \
            and _absorption_sell(rates, poc, tolerance, strict=strict):
        entry = round(poc, 2)
        sl    = round(cur_high + sl_buf, 2)
        tp    = _tp_sell(rates, entry, sl, val)
        if tp and tp < entry < sl and entry > cur_close:
            _mark_fired(tf, "SELL", poc, bar_time)
            results.append({
                "signal":      "SELL",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 15 VP POC 🔴 SELL — Absorption",
                "reason":      f"{vp_info}\nAbsorption ที่ POC",
                "order_mode":  "limit",
                "entry_label": "SELL LIMIT (POC Absorption)",
                "vp_poc": poc, "vp_val": val, "vp_vah": vah,
            })

    # ── SELL at VAH ─────────────────────────────────────────────────
    if allow_sell and use_val_vah and vah != poc \
            and not _level_on_cooldown(tf, "SELL", vah, bar_time, cooldown_bars, tf_secs) \
            and _absorption_sell(rates, vah, tolerance, strict=strict):
        entry = round(vah, 2)
        sl    = round(cur_high + sl_buf, 2)
        tp    = _tp_sell(rates, entry, sl, poc)
        if tp and tp < entry < sl and entry > cur_close:
            _mark_fired(tf, "SELL", vah, bar_time)
            results.append({
                "signal":      "SELL",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 15 VP VAH 🔴 SELL — Absorption",
                "reason":      f"{vp_info}\nAbsorption ที่ VAH",
                "order_mode":  "limit",
                "entry_label": "SELL LIMIT (VAH Absorption)",
                "vp_poc": poc, "vp_val": val, "vp_vah": vah,
            })

    if not results:
        return {
            "signal": "WAIT",
            "reason": f"S15: ไม่พบ Absorption — {vp_info}",
        }
    if len(results) == 1:
        return results[0]
    return {"signal": "MULTI", "orders": results}
