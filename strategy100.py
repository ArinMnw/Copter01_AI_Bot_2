# -*- coding: utf-8 -*-
"""
S100: Multi-Setup Liquidity Reversal (สายบุก — ต่อยอด S99)

แนวคิด (The Alpha):
  ใช้แกนเดียวกับ S99 ที่พิสูจน์แล้วว่ามี edge:
  Liquidity Sweep -> Displacement -> LIMIT retrace + Premium/Discount filter

  เพิ่มความถี่โดยไม่ทิ้งความแม่นด้วย "หลาย setup ในกรอบเดียว":
  1. Dual pivot — หา swing ทั้งโครงสร้างใหญ่ (3/3) และย่อย (2/2)
     sweep ของ swing ย่อยเกิดบ่อยกว่าหลายเท่า
  2. Confirmation แบบ OR (อย่างใดอย่างหนึ่งพอ):
     - FVG บน displacement (setup เดิมของ S99), หรือ
     - RSI extreme reversal — RSI ณ แท่ง sweep อยู่โซนสุดขั้ว
       (BUY <= 35 / SELL >= 65) แล้วกลับตัว = แรงขายหมด + sweep เก็บ stop พอดี
  3. Sweep age กว้างขึ้น (40 แท่ง) + displacement 1.2xATR (S99 ใช้ 1.4)
  4. RR ลดเป็น 1.5 (S99 ใช้ 1.8) — ยก win rate เชิงกลไก โดย PF ยังสูง
     (WR 65% ที่ RR 1.5 -> PF ~2.8)

  หมายเหตุ: เวอร์ชันแรกของ S100 ลอง trend-following pullback (EMA H1/M15 gate)
  แล้ว sweep 90 วันพบว่าไม่มีตัวกรองไหนพา WR เกิน 55% ได้ (เดือน choppy แดงหมด)
  จึงกลับมาใช้แกน reversal ของ S99 ที่มี edge จริง แล้วขยายความถี่แทน
"""

DEFAULT_CFG = {
    "SWING_SETS": ((3, 3), (2, 2)),  # (left, right) หลายชุด — ใหญ่ก่อน
    "SWING_SCAN_BARS": 80,
    "SWEEP_MAX_AGE": 60,
    "DISP_BODY_ATR": 1.4,
    "ENTRY_RETRACE": 0.30,  # ตื้นกว่า S99 (0.5) — fill ง่ายขึ้น แปลง signal เป็นเทรดได้มากขึ้น
    "SL_BUF_ATR": 0.35,
    "TP_RR": 1.2,  # RR ต่ำกว่า S99 (1.8) — ยก WR เชิงกลไก, 180d sweep: rr1.2 ชนะทุก half
    "PD_RANGE_BARS": 100,
    "PD_FILTER_ENABLED": True,
    "ATR_REGIME_PCTL": 25.0,
    "TIME_FILTER_ENABLED": True,
    "BLOCK_HOURS": (4, 5, 6, 12, 13),
    # confirmation (OR): FVG หรือ RSI extreme reversal
    "CONFIRM_FVG": True,
    "CONFIRM_RSI_EXTREME": True,
    "RSI_PERIOD": 14,
    "RSI_BUY_EXTREME": 30.0,   # RSI ณ แท่ง sweep ต้อง <= สำหรับ BUY
    "RSI_SELL_EXTREME": 70.0,  # RSI ณ แท่ง sweep ต้อง >= สำหรับ SELL
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
    out = [None] * len(rates)
    trs = []
    for i in range(1, len(rates)):
        h, l = float(rates[i]["high"]), float(rates[i]["low"])
        pc = float(rates[i - 1]["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        if len(trs) >= period:
            out[i] = sum(trs[-period:]) / period
    return out


def _rsi_at(closes, period=14):
    """RSI (Wilder) ของค่า close ตัวสุดท้ายใน closes"""
    if len(closes) < period + 2:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    rsi = None
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        rsi = 100.0 if avg_l == 0 else 100.0 - 100.0 / (1.0 + avg_g / avg_l)
    return rsi


def _find_swings(rates, left, right, scan_bars):
    n = len(rates)
    highs, lows = [], []
    start = max(left, n - scan_bars)
    for i in range(start, n - right):
        h = float(rates[i]["high"])
        l = float(rates[i]["low"])
        if all(float(rates[j]["high"]) < h for j in range(i - left, i + right + 1) if j != i):
            highs.append((i, h))
        if all(float(rates[j]["low"]) > l for j in range(i - left, i + right + 1) if j != i):
            lows.append((i, l))
    return highs, lows


def detect_s100(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    if len(rates) < 120:
        return {"signal": "WAIT", "reason": "Not enough data"}

    if c["TIME_FILTER_ENABLED"] and dt_bkk is not None:
        if dt_bkk.hour in c["BLOCK_HOURS"]:
            return {"signal": "WAIT", "reason": f"Blocked hour {dt_bkk.hour}"}

    atr = _atr(rates)
    if atr <= 0:
        return {"signal": "WAIT", "reason": "ATR zero"}

    if c["ATR_REGIME_PCTL"] > 0:
        series = [x for x in _atr_series(rates)[-100:] if x is not None]
        if series:
            s = sorted(series)
            k = min(max(int(len(s) * c["ATR_REGIME_PCTL"] / 100.0), 0), len(s) - 1)
            if atr < s[k]:
                return {"signal": "WAIT", "reason": "Low volatility regime"}

    n = len(rates)
    sweep_bar, disp_bar = rates[-2], rates[-1]
    sw_h, sw_l, sw_c = (float(sweep_bar["high"]), float(sweep_bar["low"]),
                        float(sweep_bar["close"]))
    d_o, d_c = float(disp_bar["open"]), float(disp_bar["close"])
    d_h, d_l = float(disp_bar["high"]), float(disp_bar["low"])
    d_body = abs(d_c - d_o)
    if d_body < atr * float(c["DISP_BODY_ATR"]):
        return {"signal": "WAIT", "reason": "Displacement too small"}

    # รวม swing จากทุก pivot set (กันซ้ำด้วย index)
    all_highs, all_lows = {}, {}
    for left, right in c["SWING_SETS"]:
        hs, ls = _find_swings(rates, int(left), int(right), int(c["SWING_SCAN_BARS"]))
        for idx, price in hs:
            all_highs[idx] = price
        for idx, price in ls:
            all_lows[idx] = price
    sw_highs = sorted(all_highs.items())
    sw_lows = sorted(all_lows.items())
    max_age = int(c["SWEEP_MAX_AGE"])

    pd_bars = rates[-int(c["PD_RANGE_BARS"]):]
    rng_h = max(float(r["high"]) for r in pd_bars)
    rng_l = min(float(r["low"]) for r in pd_bars)
    eq = (rng_h + rng_l) / 2.0

    closes = [float(r["close"]) for r in rates]
    rsi_sweep = _rsi_at(closes[-81:-1], int(c["RSI_PERIOD"]))  # RSI ณ แท่ง sweep

    def _confirm(direction):
        """FVG หรือ RSI extreme — อย่างใดอย่างหนึ่ง"""
        tags = []
        if c["CONFIRM_FVG"]:
            a = rates[-3]
            if direction == "SELL" and float(a["low"]) > d_h:
                tags.append("FVG")
            if direction == "BUY" and float(a["high"]) < d_l:
                tags.append("FVG")
        if c["CONFIRM_RSI_EXTREME"] and rsi_sweep is not None:
            if direction == "BUY" and rsi_sweep <= float(c["RSI_BUY_EXTREME"]):
                tags.append(f"RSIx{rsi_sweep:.0f}")
            if direction == "SELL" and rsi_sweep >= float(c["RSI_SELL_EXTREME"]):
                tags.append(f"RSIx{rsi_sweep:.0f}")
        return tags

    def _ml_ok(direction, entry):
        if not c["ML_FILTER_ENABLED"]:
            return True, 1.0
        import ml_scoring
        prob = ml_scoring.score_signal('XAUUSD.iux', tf, direction, entry,
                                       dt_bkk, historical_rates=rates)
        return prob >= float(c["ML_SCORE_THRESHOLD"]), prob

    # ---------- SELL ----------
    if d_c < d_o:
        swept = None
        for idx, price in reversed(sw_highs):
            if (n - 2) - idx > max_age or idx >= n - 2:
                continue
            if sw_h > price and sw_c < price:
                swept = (idx, price)
                break
        if swept and d_c < sw_c:
            if c["PD_FILTER_ENABLED"] and sw_h < eq:
                return {"signal": "WAIT", "reason": "SELL sweep not in premium"}
            tags = _confirm("SELL")
            if not tags:
                return {"signal": "WAIT", "reason": "No FVG/RSI confirmation"}
            sweep_ext = max(sw_h, d_h)
            entry = d_c + (sweep_ext - d_c) * float(c["ENTRY_RETRACE"])
            sl = sweep_ext + max(1.5, atr * float(c["SL_BUF_ATR"]))
            risk = sl - entry
            if risk <= 0:
                return {"signal": "WAIT", "reason": "Invalid risk"}
            tp = entry - risk * float(c["TP_RR"])
            ok, prob = _ml_ok("SELL", entry)
            if not ok:
                return {"signal": "WAIT", "reason": f"S100 SELL blocked by ML ({prob:.2f})"}
            return {
                "signal": "SELL",
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "tp": round(tp, 2),
                "order_type": "limit",
                "pattern": "S100 Multi-Sweep 🔴 SELL",
                "reason": (f"Swept high {swept[1]:.2f} (age {(n-2)-swept[0]}), "
                           f"disp {d_body:.2f}>={atr:.2f}x{c['DISP_BODY_ATR']}, "
                           f"confirm: {'+'.join(tags)}"),
                "candles": [sweep_bar, disp_bar],
            }

    # ---------- BUY ----------
    if d_c > d_o:
        swept = None
        for idx, price in reversed(sw_lows):
            if (n - 2) - idx > max_age or idx >= n - 2:
                continue
            if sw_l < price and sw_c > price:
                swept = (idx, price)
                break
        if swept and d_c > sw_c:
            if c["PD_FILTER_ENABLED"] and sw_l > eq:
                return {"signal": "WAIT", "reason": "BUY sweep not in discount"}
            tags = _confirm("BUY")
            if not tags:
                return {"signal": "WAIT", "reason": "No FVG/RSI confirmation"}
            sweep_ext = min(sw_l, d_l)
            entry = d_c - (d_c - sweep_ext) * float(c["ENTRY_RETRACE"])
            sl = sweep_ext - max(1.5, atr * float(c["SL_BUF_ATR"]))
            risk = entry - sl
            if risk <= 0:
                return {"signal": "WAIT", "reason": "Invalid risk"}
            tp = entry + risk * float(c["TP_RR"])
            ok, prob = _ml_ok("BUY", entry)
            if not ok:
                return {"signal": "WAIT", "reason": f"S100 BUY blocked by ML ({prob:.2f})"}
            return {
                "signal": "BUY",
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "tp": round(tp, 2),
                "order_type": "limit",
                "pattern": "S100 Multi-Sweep 🟢 BUY",
                "reason": (f"Swept low {swept[1]:.2f} (age {(n-2)-swept[0]}), "
                           f"disp {d_body:.2f}>={atr:.2f}x{c['DISP_BODY_ATR']}, "
                           f"confirm: {'+'.join(tags)}"),
                "candles": [sweep_bar, disp_bar],
            }

    return {"signal": "WAIT", "reason": "No sweep+displacement setup"}
