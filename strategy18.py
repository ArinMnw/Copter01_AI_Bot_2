"""
strategy18.py — S18 TJR / ICT Full-Confluence (Standalone)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
นำ concept การเทรดของ TJR (ICT-based) มารวมเป็น 1 ท่า แบบ "ครบทุกชั้นจึงเข้า"

ลำดับ Confluence (ต้องผ่านครบ):
  1. Killzone   : เทรดเฉพาะช่วง London/NY (S18_SESSIONS)
  2. HTF Bias   : เทรดตามทิศ HTF (M1→M15, M5→H1 ...) จาก hhll_swing structure
  3. Liquidity Sweep : ไส้กวาด swing low (BUY) / swing high (SELL) แล้วปฏิเสธ
  4. MSS / CHOCH: หลัง sweep ราคา *close* ทะลุ internal structure ในทิศ bias
  5. Entry Zone : FVG หรือ Order Block ที่อยู่ในแถบ OTE (62–79%) ของ leg sweep→MSS
  6. RSI confirm (optional)
  7. SL/TP/Guard: SL หลังไส้ sweep | TP ที่ opposing liquidity ตาม RR เป้า

Entry: LIMIT รอ retrace เข้าโซน FVG/OB — ไม่ fill ใน S18_LIMIT_CANCEL_BARS แท่ง → cancel
Standalone — bypass trend/PD recheck กลาง (เหมือน S14/S15/S16/S17)
comment: <TF>_S18_TJB / <TF>_S18_TJS

หมายเหตุ: detector FVG/OB/MSS เป็น helper ภายในไฟล์นี้ (ย้ายไป smc_zones.py ได้
ภายหลังถ้า S19+ ต้องใช้ร่วม). ค่า default ของ S18_* เป็นค่าตั้งต้นก่อน backtest
— ปรับจูนหลังรัน sim_s18_backtest.py จริง (เหมือน S16/S17)
"""

from datetime import time

import config
from mt5_utils import calc_atr

# ── dedup state (in-memory — ไม่ persist ข้าม restart) ──────────────
_s18_last_fire: dict = {}    # (tf, side) → sweep bar time ที่ fire ล่าสุด
_s18_level_fired: dict = {}  # (tf, side, level ปัด 1 ตำแหน่ง) → sweep bar time

_TF_SECS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
}

# entry TF → bias TF (ถ้าไม่มีใน map ใช้ M15)
_S18_HTF_MAP = {
    "M1": "M15", "M5": "H1", "M15": "H1",
    "M30": "H4", "H1": "H4", "H4": "D1",
}


# ─────────────────────────────────────────────────────────────────────────────
# Indicators / helpers
# ─────────────────────────────────────────────────────────────────────────────
def _calc_rsi(rates, period=14):
    """RSI แบบ Wilder's smoothing (เหมือน S15/S17) — ใช้ close ของ rates ที่ส่งมา"""
    if len(rates) < period + 1:
        return None
    closes = [float(r["close"]) for r in rates[-(period * 3):]]
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    if len(gains) < period:
        return None
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def _in_session(dt_bkk) -> bool:
    """เช็คว่าเวลา BKK อยู่ใน S18_SESSIONS (Killzones) หรือไม่"""
    if not getattr(config, "S18_SESSION_FILTER", True):
        return True
    cur = dt_bkk.time()
    for start_str, end_str in getattr(
        config, "S18_SESSIONS", [("14:00", "18:00"), ("19:00", "23:00")]
    ):
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        if time(sh, sm) <= cur < time(eh, em):
            return True
    return False


def _pivots(rates, lo, hi):
    """3-bar pivot ภายใน rates[lo:hi] (ไม่บังคับสีแท่ง)
    คืน (highs, lows) = list ของ (idx, price) เรียงตาม idx (เก่า→ใหม่)"""
    highs, lows = [], []
    for i in range(lo + 1, hi - 1):
        h, ph, nh = float(rates[i]["high"]), float(rates[i - 1]["high"]), float(rates[i + 1]["high"])
        l, pl, nl = float(rates[i]["low"]),  float(rates[i - 1]["low"]),  float(rates[i + 1]["low"])
        if h > ph and h > nh:
            highs.append((i, h))
        if l < pl and l < nl:
            lows.append((i, l))
    return highs, lows


def _find_fvg(rates, direction, lo, hi):
    """หา Fair Value Gap (3-candle imbalance) ใน rates[lo:hi] คืนโซน "ใหม่สุด"
    bullish (BUY): low[i] > high[i-2]  → zone = (high[i-2], low[i])
    bearish (SELL): high[i] < low[i-2] → zone = (high[i], low[i-2])
    return {"top","bottom","mid","bar_idx"} หรือ None"""
    for i in range(hi - 1, lo + 1, -1):
        h2 = float(rates[i - 2]["high"])
        l2 = float(rates[i - 2]["low"])
        hi_ = float(rates[i]["high"])
        lo_ = float(rates[i]["low"])
        if direction == "BUY" and lo_ > h2:
            return {"top": lo_, "bottom": h2, "mid": (lo_ + h2) / 2.0, "bar_idx": i}
        if direction == "SELL" and hi_ < l2:
            return {"top": l2, "bottom": hi_, "mid": (l2 + hi_) / 2.0, "bar_idx": i}
    return None


def _find_ob(rates, direction, lo, mss_idx):
    """หา Order Block: แท่งตรงข้ามตัวสุดท้ายก่อน impulsive move ที่ทำ MSS
    bullish OB (BUY): แท่งแดง (close<open) ตัวสุดท้ายก่อน move ขึ้น
    bearish OB (SELL): แท่งเขียว (close>open) ตัวสุดท้ายก่อน move ลง
    zone = (high, low) ของแท่งนั้น; return {"top","bottom","mid","bar_idx"} หรือ None"""
    for i in range(mss_idx, lo, -1):
        o, c = float(rates[i]["open"]), float(rates[i]["close"])
        h, l = float(rates[i]["high"]), float(rates[i]["low"])
        if direction == "BUY" and c < o:
            return {"top": h, "bottom": l, "mid": (h + l) / 2.0, "bar_idx": i}
        if direction == "SELL" and c > o:
            return {"top": h, "bottom": l, "mid": (h + l) / 2.0, "bar_idx": i}
    return None


def _bias_from_rates(htf_rates):
    """ประเมิน bias จาก HTF rates ด้วย 2 pivot ล่าสุด (BULL/BEAR/SIDEWAY/UNKNOWN)"""
    if htf_rates is None or len(htf_rates) < 10:
        return "UNKNOWN"
    highs, lows = _pivots(htf_rates, 0, len(htf_rates))
    if len(highs) < 2 or len(lows) < 2:
        return "UNKNOWN"
    h0, h1 = highs[-1][1], highs[-2][1]
    l0, l1 = lows[-1][1], lows[-2][1]
    if h0 > h1 and l0 > l1:
        return "BULL"
    if h0 < h1 and l0 < l1:
        return "BEAR"
    return "SIDEWAY"


def _get_htf_bias(tf, htf_rates=None):
    """คืน "BULL"/"BEAR"/"SIDEWAY"/"UNKNOWN" ของ HTF ที่ map กับ tf
    - backtest/sim: ส่ง htf_rates มา → คำนวณตรง (กัน look-ahead)
    - runtime: ใช้ cache hhll_swing (อุ่นจาก scanner) → fallback fetch สด
    """
    if htf_rates is not None:
        return _bias_from_rates(htf_rates)

    htf_map = getattr(config, "S18_HTF_MAP", _S18_HTF_MAP)
    htf_tf = htf_map.get(tf, "M15")

    try:
        import hhll_swing as _hs
        t = _hs.get_trend_from_structure(htf_tf)
        if t and t.get("trend") in ("BULL", "BEAR", "SIDEWAY"):
            return t["trend"]
    except Exception:
        pass

    # fallback: ดึง HTF สด (แบบ amp_trend/S14)
    try:
        import MetaTrader5 as mt5
        tfval = config.TF_OPTIONS.get(htf_tf)
        if tfval is not None:
            hr = mt5.copy_rates_from_pos(config.SYMBOL, tfval, 0, 200)
            if hr is not None and len(hr):
                return _bias_from_rates(hr)
    except Exception:
        pass
    return "UNKNOWN"


def _zone_overlaps(zone, lo, hi) -> bool:
    """โซน [bottom,top] ทับกับช่วง OTE [lo,hi] หรือไม่"""
    return zone is not None and zone["bottom"] <= hi and zone["top"] >= lo


# ─────────────────────────────────────────────────────────────────────────────
# Pure detector
# ─────────────────────────────────────────────────────────────────────────────
def detect_s18(rates, tf: str = "", dt_bkk=None, htf_rates=None):
    """
    Pure detection — ไม่แตะ dedup state (backtest เรียกตรงได้)
    rates: แท่งสุดท้าย = แท่งกำลังวิ่ง, rates[-2] = แท่งปิดล่าสุด
    คืน dict {signal: BUY/SELL/WAIT, ...} แบบเดียวกับ strategy อื่น
    """
    lookback = int(getattr(config, "S18_LOOKBACK", 60))
    n = len(rates) if rates is not None else 0
    if rates is None or n < lookback + 5:
        return {"signal": "WAIT", "reason": f"S18: ข้อมูลไม่พอ (ต้องการ ≥ {lookback + 5} แท่ง)"}

    # 1) Killzone
    if dt_bkk is not None and not _in_session(dt_bkk):
        return {"signal": "WAIT", "reason": "S18: อยู่นอกช่วง Killzones London/NY"}

    # 3) ATR / RSI
    atr = calc_atr(rates[:-1], 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S18: คำนวณ ATR ไม่ได้"}
    rsi = _calc_rsi(rates[:-1], int(getattr(config, "S18_RSI_PERIOD", 14)))
    if rsi is None:
        return {"signal": "WAIT", "reason": "S18: คำนวณ RSI ไม่ได้"}

    # 2) HTF bias
    bias = _get_htf_bias(tf, htf_rates)
    require_bias = bool(getattr(config, "S18_REQUIRE_HTF_BIAS", True))
    htf_map = getattr(config, "S18_HTF_MAP", _S18_HTF_MAP)
    htf_tf = htf_map.get(tf, "M15")
    if require_bias and bias not in ("BULL", "BEAR"):
        return {"signal": "WAIT", "reason": f"S18: HTF {htf_tf} bias = {bias} (ไม่อยู่ในทิศเทรด)"}

    sig_idx = n - 2                     # แท่งปิดล่าสุด
    seg_lo = max(0, sig_idx - lookback)
    highs, lows = _pivots(rates, seg_lo, n - 1)

    cur_price = float(rates[-1]["close"])
    ote_lo_pct = float(getattr(config, "S18_OTE_LO", 0.62))
    ote_hi_pct = float(getattr(config, "S18_OTE_HI", 0.79))
    sl_buf = atr * float(getattr(config, "S18_SL_ATR_BUFFER", 1.0))
    rr_target = float(getattr(config, "S18_RR_TARGET", 2.0))
    min_rr = float(getattr(config, "S18_MIN_RR", 1.5))
    max_risk_mult = float(getattr(config, "S18_MAX_RISK_ATR_MULT", 6.0))
    rsi_filter = bool(getattr(config, "S18_RSI_FILTER", True))
    rsi_buy_max = float(getattr(config, "S18_RSI_BUY_MAX", 45))
    rsi_sell_min = float(getattr(config, "S18_RSI_SELL_MIN", 55))
    zone_prefer = str(getattr(config, "S18_ZONE_PREFER", "fvg")).lower()
    entry_mode = str(getattr(config, "S18_ENTRY_MODE", "zone_edge")).lower()
    cancel_bars = int(getattr(config, "S18_LIMIT_CANCEL_BARS", 8))
    candles = list(rates[-4:-1])

    # ── BUY chain (ต้อง bias BULL) ──────────────────────────────────
    if (not require_bias and bias != "BEAR") or bias == "BULL":
        if len(lows) >= 2 and len(highs) >= 1:
            i_s, swept_low = lows[-1]
            prev_low = lows[-2][1]
            # sweep = ไส้ต่ำกว่า low ก่อนหน้า (เก็บ liquidity ใต้)
            if swept_low < prev_low:
                # MSS: หา pivot high ก่อน sweep แล้วเช็คว่ามีแท่ง close ทะลุขึ้น
                struct_highs = [(idx, p) for idx, p in highs if idx < i_s]
                if struct_highs:
                    h_idx, h_struct = struct_highs[-1]
                    mss_idx = None
                    for j in range(i_s + 1, n - 1):
                        if float(rates[j]["close"]) > h_struct:
                            mss_idx = j
                            break
                    if mss_idx is not None:
                        leg_high = max(float(rates[k]["high"]) for k in range(i_s, n - 1))
                        leg = leg_high - swept_low
                        if leg > 0:
                            ote_hi = leg_high - ote_lo_pct * leg   # 62% (ราคาสูงกว่า)
                            ote_lo = leg_high - ote_hi_pct * leg   # 79% (ราคาต่ำกว่า)
                            fvg = _find_fvg(rates, "BUY", i_s, n - 1)
                            ob = _find_ob(rates, "BUY", seg_lo, mss_idx)
                            order = [fvg, ob] if zone_prefer == "fvg" else [ob, fvg]
                            zone = next((z for z in order if _zone_overlaps(z, ote_lo, ote_hi)), None)
                            ztype = "FVG" if zone is fvg and fvg is not None else ("OB" if zone is not None else None)
                            if zone is None:
                                return {"signal": "WAIT", "reason": "S18: ไม่มี FVG/OB ใน OTE zone (BUY)"}
                            if rsi_filter and rsi > rsi_buy_max:
                                return {"signal": "WAIT", "reason": f"S18: RSI `{rsi:.1f}` > {rsi_buy_max:.0f} (BUY ไม่ยืนยัน)"}
                            zone_top = min(zone["top"], ote_hi)
                            entry = round(zone_top if entry_mode == "zone_edge"
                                          else max(min(zone["mid"], ote_hi), ote_lo), 2)
                            sl = round(swept_low - sl_buf, 2)
                            risk = entry - sl
                            tps = [p for _, p in highs if p > entry]
                            tp_liq = min(tps) if tps else None
                            if tp_liq is not None and risk > 0 and (tp_liq - entry) / risk >= min_rr:
                                tp = round(tp_liq, 2)
                            else:
                                tp = round(entry + rr_target * risk, 2)
                            rr = (tp - entry) / risk if risk > 0 else 0
                            if not (0 < risk <= max_risk_mult * atr):
                                return {"signal": "WAIT", "reason": f"S18: risk `{risk:.2f}` เกิน {max_risk_mult}×ATR (BUY)"}
                            if rr < min_rr:
                                return {"signal": "WAIT", "reason": f"S18: RR `{rr:.2f}` < {min_rr} (BUY)"}
                            if cur_price <= entry:
                                return {"signal": "WAIT", "reason": "S18: ราคาต่ำกว่าโซน entry แล้ว (BUY stale)"}
                            return {
                                "signal":      "BUY",
                                "entry":       entry,
                                "sl":          sl,
                                "tp":          tp,
                                "pattern":     "ท่าที่ 18 TJR ICT 🟢 BUY",
                                "reason": (
                                    f"HTF {htf_tf}=BULL | Sweep Low `{swept_low:.2f}` < prev `{prev_low:.2f}`\n"
                                    f"MSS: close ทะลุ structure high `{h_struct:.2f}` ✓\n"
                                    f"Entry zone {ztype} ใน OTE `{ote_lo:.2f}`–`{ote_hi:.2f}` (62–79%)\n"
                                    f"RSI `{rsi:.1f}` | RR `{rr:.2f}` | SL ใต้ไส้ sweep"
                                ),
                                "order_mode":  "limit",
                                "entry_label": f"BUY LIMIT (TJR {ztype} OTE)",
                                "candles":     candles,
                                "cancel_bars": cancel_bars,
                                "sweep_level": round(swept_low, 2),
                                "sweep_bar_time": int(rates[i_s]["time"]),
                                "htf_bias":    bias,
                                "mss_level":   round(h_struct, 2),
                                "zone_type":   ztype,
                                "rsi_at_signal": rsi,
                            }

    # ── SELL chain (ต้อง bias BEAR) ─────────────────────────────────
    if (not require_bias and bias != "BULL") or bias == "BEAR":
        if len(highs) >= 2 and len(lows) >= 1:
            i_s, swept_high = highs[-1]
            prev_high = highs[-2][1]
            if swept_high > prev_high:
                struct_lows = [(idx, p) for idx, p in lows if idx < i_s]
                if struct_lows:
                    l_idx, l_struct = struct_lows[-1]
                    mss_idx = None
                    for j in range(i_s + 1, n - 1):
                        if float(rates[j]["close"]) < l_struct:
                            mss_idx = j
                            break
                    if mss_idx is not None:
                        leg_low = min(float(rates[k]["low"]) for k in range(i_s, n - 1))
                        leg = swept_high - leg_low
                        if leg > 0:
                            ote_lo = leg_low + ote_lo_pct * leg   # 62% (ราคาต่ำกว่า)
                            ote_hi = leg_low + ote_hi_pct * leg   # 79% (ราคาสูงกว่า)
                            fvg = _find_fvg(rates, "SELL", i_s, n - 1)
                            ob = _find_ob(rates, "SELL", seg_lo, mss_idx)
                            order = [fvg, ob] if zone_prefer == "fvg" else [ob, fvg]
                            zone = next((z for z in order if _zone_overlaps(z, ote_lo, ote_hi)), None)
                            ztype = "FVG" if zone is fvg and fvg is not None else ("OB" if zone is not None else None)
                            if zone is None:
                                return {"signal": "WAIT", "reason": "S18: ไม่มี FVG/OB ใน OTE zone (SELL)"}
                            if rsi_filter and rsi < rsi_sell_min:
                                return {"signal": "WAIT", "reason": f"S18: RSI `{rsi:.1f}` < {rsi_sell_min:.0f} (SELL ไม่ยืนยัน)"}
                            zone_bot = max(zone["bottom"], ote_lo)
                            entry = round(zone_bot if entry_mode == "zone_edge"
                                          else min(max(zone["mid"], ote_lo), ote_hi), 2)
                            sl = round(swept_high + sl_buf, 2)
                            risk = sl - entry
                            tps = [p for _, p in lows if p < entry]
                            tp_liq = max(tps) if tps else None
                            if tp_liq is not None and risk > 0 and (entry - tp_liq) / risk >= min_rr:
                                tp = round(tp_liq, 2)
                            else:
                                tp = round(entry - rr_target * risk, 2)
                            rr = (entry - tp) / risk if risk > 0 else 0
                            if not (0 < risk <= max_risk_mult * atr):
                                return {"signal": "WAIT", "reason": f"S18: risk `{risk:.2f}` เกิน {max_risk_mult}×ATR (SELL)"}
                            if rr < min_rr:
                                return {"signal": "WAIT", "reason": f"S18: RR `{rr:.2f}` < {min_rr} (SELL)"}
                            if cur_price >= entry:
                                return {"signal": "WAIT", "reason": "S18: ราคาสูงกว่าโซน entry แล้ว (SELL stale)"}
                            return {
                                "signal":      "SELL",
                                "entry":       entry,
                                "sl":          sl,
                                "tp":          tp,
                                "pattern":     "ท่าที่ 18 TJR ICT 🔴 SELL",
                                "reason": (
                                    f"HTF {htf_tf}=BEAR | Sweep High `{swept_high:.2f}` > prev `{prev_high:.2f}`\n"
                                    f"MSS: close ทะลุ structure low `{l_struct:.2f}` ✓\n"
                                    f"Entry zone {ztype} ใน OTE `{ote_lo:.2f}`–`{ote_hi:.2f}` (62–79%)\n"
                                    f"RSI `{rsi:.1f}` | RR `{rr:.2f}` | SL เหนือไส้ sweep"
                                ),
                                "order_mode":  "limit",
                                "entry_label": f"SELL LIMIT (TJR {ztype} OTE)",
                                "candles":     candles,
                                "cancel_bars": cancel_bars,
                                "sweep_level": round(swept_high, 2),
                                "sweep_bar_time": int(rates[i_s]["time"]),
                                "htf_bias":    bias,
                                "mss_level":   round(l_struct, 2),
                                "zone_type":   ztype,
                                "rsi_at_signal": rsi,
                            }

    return {"signal": "WAIT", "reason": "S18: ยังไม่ครบ sweep→MSS→FVG/OB ใน OTE"}


# ─────────────────────────────────────────────────────────────────────────────
# Runtime wrapper
# ─────────────────────────────────────────────────────────────────────────────
def strategy_18(rates, tf: str = "", htf_rates=None):
    """
    S18: TJR/ICT — wrapper runtime (TF gate + dedup + session ด้วยเวลาปัจจุบัน)
    """
    allowed_tfs = getattr(config, "S18_ALLOWED_TFS", ["M1", "M5"])
    if allowed_tfs and tf not in allowed_tfs:
        return {"signal": "WAIT", "reason": f"S18: ใช้เฉพาะ TF {','.join(allowed_tfs)}"}

    result = detect_s18(rates, tf=tf, dt_bkk=config.now_bkk(), htf_rates=htf_rates)
    sig = result.get("signal")
    if sig not in ("BUY", "SELL"):
        return result

    bar_time = int(result.get("sweep_bar_time", 0))
    level = float(result.get("sweep_level", 0.0))

    # กัน re-fire sweep เดิมระหว่างรอบ scan (scanner วนทุก 5 วินาที)
    if _s18_last_fire.get((tf, sig)) == bar_time:
        return {"signal": "WAIT", "reason": "S18: fire sweep นี้ไปแล้ว (dedup)"}

    # กันยิงซ้ำ level เดิมภายใน S18_LEVEL_COOLDOWN_BARS แท่ง
    cooldown_bars = int(getattr(config, "S18_LEVEL_COOLDOWN_BARS", 20))
    tf_secs = _TF_SECS.get(tf, 60)
    lv_key = (tf, sig, round(level, 1))
    last_lv_time = _s18_level_fired.get(lv_key, 0)
    if last_lv_time and (bar_time - last_lv_time) < cooldown_bars * tf_secs:
        return {"signal": "WAIT", "reason": f"S18: level `{level:.1f}` อยู่ใน cooldown {cooldown_bars} แท่ง"}

    _s18_last_fire[(tf, sig)] = bar_time
    _s18_level_fired[lv_key] = bar_time
    return result
