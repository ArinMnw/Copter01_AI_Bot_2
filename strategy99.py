# -*- coding: utf-8 -*-
"""
S99: Sweep + Displacement + FVG Retrace (SMC Confluence)

แนวคิด (The Alpha):
  1. Liquidity Sweep — ราคาไล่กวาด stop เหนือ swing high / ใต้ swing low
     (wick ทะลุ แต่ close กลับเข้ามาใน range) = smart money เก็บ liquidity
  2. Displacement — แท่งถัดมาต้องมี body ใหญ่ (>= ATR x mult) วิ่งสวนทาง sweep
     ยืนยันว่ามี order flow จริง ไม่ใช่แค่ wick ธรรมดา
  3. FVG Retrace — แท่ง displacement มักทิ้ง Fair Value Gap ไว้
     เข้า LIMIT ที่ 50% ของ displacement leg (หรือขอบ FVG) แทนไล่ราคา
  4. Premium/Discount — SELL เฉพาะโซน premium, BUY เฉพาะโซน discount
     ของ range 100 แท่งล่าสุด
  5. Volatility Regime — ข้ามช่วงตลาดตาย (ATR ต่ำกว่า percentile ที่กำหนด)

ต่างจาก S95 (sweep + ML): S99 บังคับ displacement + entry แบบ retrace limit
ต่างจาก S96 (PoC pullback): S99 เป็น reversal ที่จุด liquidity ไม่ใช่ trend-follow
"""

DEFAULT_CFG = {
    "SWING_LEFT": 3,           # pivot lookback ซ้าย
    "SWING_RIGHT": 3,          # pivot lookback ขวา
    "SWING_SCAN_BARS": 80,     # หา swing ย้อนหลังกี่แท่ง
    "SWEEP_MAX_AGE": 25,       # swing ต้องเกิดไม่เกินกี่แท่งก่อนหน้า (ความสด)
    "DISP_BODY_ATR": 1.4,      # body ของแท่ง displacement >= ATR x ค่านี้
                               # (sweep 180d: 1.4+FVG → WR 64.7% PF 3.88; 1.2 → เทรดถี่ขึ้นแต่ WR 48.6%)
    "ENTRY_RETRACE": 0.5,      # เข้า limit ที่ retrace กี่ % ของ displacement leg
    "SL_BUF_ATR": 0.35,        # buffer SL หลัง sweep extreme (x ATR)
    "TP_RR": 1.8,              # Risk:Reward
    "PD_RANGE_BARS": 100,      # range สำหรับ premium/discount
    "PD_FILTER_ENABLED": True,
    "ATR_REGIME_PCTL": 25.0,   # ATR ปัจจุบันต้อง > percentile นี้ของ ATR ย้อนหลัง
    "TIME_FILTER_ENABLED": True,
    "BLOCK_HOURS": (4, 5, 6, 12, 13),  # ชั่วโมง BKK ที่ sweep มัก fake (ตลาดเบา/เที่ยงเอเชีย)
    "REQUIRE_FVG": True,       # บังคับต้องมี FVG จริงบน displacement (คัดเฉพาะ order flow แท้)
    "ML_FILTER_ENABLED": False,
    "ML_SCORE_THRESHOLD": 0.55,
}


def _atr(rates, period=14):
    trs = []
    for i in range(len(rates) - period, len(rates)):
        h, l = float(rates[i]["high"]), float(rates[i]["low"])
        pc = float(rates[i - 1]["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs)


def _atr_series(rates, period=14):
    """ATR อย่างง่าย (SMA ของ TR) คืน list ยาวเท่า rates (ช่วงต้นเป็น None)"""
    out = [None] * len(rates)
    trs = []
    for i in range(1, len(rates)):
        h, l = float(rates[i]["high"]), float(rates[i]["low"])
        pc = float(rates[i - 1]["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        if len(trs) >= period:
            out[i] = sum(trs[-period:]) / period
    return out


def _find_swings(rates, left, right, scan_bars):
    """คืน (swing_highs, swing_lows) เป็น list ของ (index, price)
    index อ้างอิงตำแหน่งใน rates; ข้ามแท่งท้ายๆ ที่ยังยืนยัน pivot ไม่ได้"""
    n = len(rates)
    highs, lows = [], []
    start = max(left, n - scan_bars)
    for i in range(start, n - right):
        h = float(rates[i]["high"])
        l = float(rates[i]["low"])
        is_h = all(float(rates[j]["high"]) < h
                   for j in range(i - left, i + right + 1) if j != i)
        is_l = all(float(rates[j]["low"]) > l
                   for j in range(i - left, i + right + 1) if j != i)
        if is_h:
            highs.append((i, h))
        if is_l:
            lows.append((i, l))
    return highs, lows


def detect_s99(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    if len(rates) < 120:
        return {"signal": "WAIT", "reason": "Not enough data"}

    # --- Time filter ---
    if c["TIME_FILTER_ENABLED"] and dt_bkk is not None:
        if dt_bkk.hour in c["BLOCK_HOURS"]:
            return {"signal": "WAIT", "reason": f"Blocked hour {dt_bkk.hour}"}

    n = len(rates)
    atr = _atr(rates)
    if atr <= 0:
        return {"signal": "WAIT", "reason": "ATR zero"}

    # --- Volatility regime: ตลาดต้องไม่ตาย ---
    if c["ATR_REGIME_PCTL"] > 0:
        series = [x for x in _atr_series(rates)[-100:] if x is not None]
        if series:
            sorted_atr = sorted(series)
            k = int(len(sorted_atr) * c["ATR_REGIME_PCTL"] / 100.0)
            k = min(max(k, 0), len(sorted_atr) - 1)
            if atr < sorted_atr[k]:
                return {"signal": "WAIT", "reason": "Low volatility regime"}

    # --- Swings ---
    sw_highs, sw_lows = _find_swings(
        rates, int(c["SWING_LEFT"]), int(c["SWING_RIGHT"]), int(c["SWING_SCAN_BARS"]))

    # แท่งที่พิจารณา: [-2] = แท่ง sweep, [-1] = แท่ง displacement (เพิ่งปิด)
    sweep_bar = rates[-2]
    disp_bar = rates[-1]
    sw_h = float(sweep_bar["high"])
    sw_l = float(sweep_bar["low"])
    sw_c = float(sweep_bar["close"])
    d_o = float(disp_bar["open"])
    d_c = float(disp_bar["close"])
    d_h = float(disp_bar["high"])
    d_l = float(disp_bar["low"])
    d_body = abs(d_c - d_o)

    # Premium/Discount ของ range ล่าสุด
    pd_bars = rates[-int(c["PD_RANGE_BARS"]):]
    rng_h = max(float(r["high"]) for r in pd_bars)
    rng_l = min(float(r["low"]) for r in pd_bars)
    eq = (rng_h + rng_l) / 2.0

    max_age = int(c["SWEEP_MAX_AGE"])
    disp_ok = d_body >= atr * float(c["DISP_BODY_ATR"])

    def _fvg_ok(direction):
        """FVG 3 แท่งท้าย: gap ระหว่างแท่ง [-3] กับ [-1] ที่แท่ง [-2]/[-1] ทิ้งไว้"""
        if not c["REQUIRE_FVG"]:
            return True
        a = rates[-3]
        if direction == "SELL":
            return float(a["low"]) > d_h  # gap ลง
        return float(a["high"]) < d_l     # gap ขึ้น

    # ---------- SELL: sweep เหนือ swing high แล้ว displacement ลง ----------
    if disp_ok and d_c < d_o:
        swept = None
        for idx, price in reversed(sw_highs):
            if (n - 2) - idx > max_age:
                continue
            if idx >= n - 2:
                continue
            # wick ทะลุ high เดิม แต่ close กลับลงมาใต้
            if sw_h > price and sw_c < price:
                swept = (idx, price)
                break
        if swept and d_c < sw_c:  # displacement ต่อเนื่องลงจริง
            if c["PD_FILTER_ENABLED"] and sw_h < eq:
                return {"signal": "WAIT", "reason": "SELL sweep not in premium"}
            if not _fvg_ok("SELL"):
                return {"signal": "WAIT", "reason": "No FVG on displacement"}

            sweep_ext = max(sw_h, d_h)
            leg_hi = sweep_ext
            leg_lo = d_c
            entry = leg_lo + (leg_hi - leg_lo) * float(c["ENTRY_RETRACE"])
            sl = sweep_ext + max(1.5, atr * float(c["SL_BUF_ATR"]))
            risk = sl - entry
            if risk <= 0:
                return {"signal": "WAIT", "reason": "Invalid risk"}
            tp = entry - risk * float(c["TP_RR"])

            if c["ML_FILTER_ENABLED"]:
                import ml_scoring
                prob = ml_scoring.score_signal('XAUUSD.iux', tf, 'SELL', entry,
                                               dt_bkk, historical_rates=rates)
                if prob < float(c["ML_SCORE_THRESHOLD"]):
                    return {"signal": "WAIT",
                            "reason": f"S99 SELL blocked by ML ({prob:.2f})"}

            return {
                "signal": "SELL",
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "tp": round(tp, 2),
                "order_type": "limit",
                "pattern": "S99 Sweep+Disp 🔴 SELL",
                "reason": (f"Swept high {swept[1]:.2f} (age {(n-2)-swept[0]} bars), "
                           f"displacement body {d_body:.2f} >= {atr:.2f}x{c['DISP_BODY_ATR']}, "
                           f"retrace entry {float(c['ENTRY_RETRACE'])*100:.0f}%"),
                "candles": [sweep_bar, disp_bar],
            }

    # ---------- BUY: sweep ใต้ swing low แล้ว displacement ขึ้น ----------
    if disp_ok and d_c > d_o:
        swept = None
        for idx, price in reversed(sw_lows):
            if (n - 2) - idx > max_age:
                continue
            if idx >= n - 2:
                continue
            if sw_l < price and sw_c > price:
                swept = (idx, price)
                break
        if swept and d_c > sw_c:
            if c["PD_FILTER_ENABLED"] and sw_l > eq:
                return {"signal": "WAIT", "reason": "BUY sweep not in discount"}
            if not _fvg_ok("BUY"):
                return {"signal": "WAIT", "reason": "No FVG on displacement"}

            sweep_ext = min(sw_l, d_l)
            leg_lo = sweep_ext
            leg_hi = d_c
            entry = leg_hi - (leg_hi - leg_lo) * float(c["ENTRY_RETRACE"])
            sl = sweep_ext - max(1.5, atr * float(c["SL_BUF_ATR"]))
            risk = entry - sl
            if risk <= 0:
                return {"signal": "WAIT", "reason": "Invalid risk"}
            tp = entry + risk * float(c["TP_RR"])

            if c["ML_FILTER_ENABLED"]:
                import ml_scoring
                prob = ml_scoring.score_signal('XAUUSD.iux', tf, 'BUY', entry,
                                               dt_bkk, historical_rates=rates)
                if prob < float(c["ML_SCORE_THRESHOLD"]):
                    return {"signal": "WAIT",
                            "reason": f"S99 BUY blocked by ML ({prob:.2f})"}

            return {
                "signal": "BUY",
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "tp": round(tp, 2),
                "order_type": "limit",
                "pattern": "S99 Sweep+Disp 🟢 BUY",
                "reason": (f"Swept low {swept[1]:.2f} (age {(n-2)-swept[0]} bars), "
                           f"displacement body {d_body:.2f} >= {atr:.2f}x{c['DISP_BODY_ATR']}, "
                           f"retrace entry {float(c['ENTRY_RETRACE'])*100:.0f}%"),
                "candles": [sweep_bar, disp_bar],
            }

    return {"signal": "WAIT", "reason": "No sweep+displacement setup"}
