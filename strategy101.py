# -*- coding: utf-8 -*-
"""
S101: High-Frequency Liquidity Reversal + Dynamic Trailing (วิวัฒนาการจาก S100)

สิ่งที่ปรับจาก S100 (และทำไม):

1. แหล่ง Liquidity เพิ่มขึ้น (ความถี่ +) —
   S100 มองแค่ swing pivot (3/3)+(2/2) แต่ smart money ล่า stop ที่:
   - PDH/PDL — Previous Day High/Low (โซน stop ใหญ่ที่สุดของ retail)
   - EQH/EQL — Equal Highs/Lows (double top/bottom ±tolerance) ที่ stop กองหนาแน่น
   sweep ของ level พวกนี้มีน้ำหนักเท่า swing ใหญ่ → ได้ setup เพิ่มโดยไม่ลดคุณภาพ

2. Adaptive Displacement (ความถี่ + โดยไม่ทิ้งความแม่น) —
   S100 บังคับ body >= 1.4xATR เสมอ
   S101: ถ้า confirmation ซ้อน 2 ชั้น (มีทั้ง FVG และ RSI extreme) → ยอมรับ
   displacement 1.1xATR ได้ เพราะหลักฐานอื่นแน่นพอ / ถ้ามีชั้นเดียว → คง 1.4xATR

3. Dynamic Trailing (รีด RR — let profit run) —
   TP fixed RR 1.2 ของ S100 ทิ้งกำไรก้อนใหญ่เวลา reversal กลายเป็นเทรนด์
   S101 ส่งพารามิเตอร์ trailing ไปกับ signal:
   - ราคาวิ่งถึง +1R → เลื่อน SL ไป breakeven
   - จากนั้น trail SL ตาม close - TRAIL_ATR_MULT*ATR (BUY) / + (SELL)
   - TP ขยับไป TP_RR_MAX (3R) — ให้ trailing เป็นตัวปิดไม้แทน TP ใกล้
   (backtester จำลองให้; ระบบ live ใช้กลไก trailing ของ trailing.py ได้)

โครงหลักยังเป็นแกน S99/S100 ที่พิสูจน์แล้ว: sweep -> displacement -> LIMIT retrace
+ Premium/Discount + ATR regime + block hours
"""

DEFAULT_CFG = {
    # liquidity sources
    "SWING_SETS": ((3, 3), (2, 2)),
    "SWING_SCAN_BARS": 80,
    "SWEEP_MAX_AGE": 60,
    "USE_PDH_PDL": True,        # previous day high/low เป็น liquidity pool
    "USE_EQ_CLUSTERS": False,   # equal highs/lows — sweep 180d พบว่าลด WR เล็กน้อย จึงปิด default
    "EQ_TOL_ATR": 0.25,         # ความห่างสูงสุดของ EQH/EQL (x ATR)
    # displacement (adaptive)
    "DISP_BODY_ATR": 1.4,       # เกณฑ์ปกติ (confirmation ชั้นเดียว)
    "DISP_BODY_ATR_STACKED": 1.1,  # เกณฑ์เมื่อ FVG + RSI extreme ครบทั้งคู่
    # confirmation
    "CONFIRM_FVG": True,
    "CONFIRM_RSI_EXTREME": True,
    "RSI_PERIOD": 14,
    "RSI_BUY_EXTREME": 30.0,
    "RSI_SELL_EXTREME": 70.0,
    # entry / risk
    "ENTRY_RETRACE": 0.30,
    "SL_BUF_ATR": 0.35,
    "TP_RR": 1.2,               # ใช้เมื่อ TRAIL_ENABLED=False
    # dynamic trailing
    "TRAIL_ENABLED": True,
    "TRAIL_BE_RR": 1.0,         # ถึง +1R → SL ไป breakeven
    "TRAIL_ATR_MULT": 1.2,      # trail SL ห่างจาก close กี่ ATR (sweep: 1.2 > 1.6 > 2.0)
    "TP_RR_MAX": 3.0,           # เพดาน TP เมื่อเปิด trailing
    # filters (เหมือน S100)
    "PD_RANGE_BARS": 100,
    "PD_FILTER_ENABLED": True,
    "ATR_REGIME_PCTL": 25.0,
    "TIME_FILTER_ENABLED": True,
    "BLOCK_HOURS": (4, 5, 6),  # ปลดชั่วโมง 12-13 ของ S99/S100 — sweep พบว่า block แค่เช้าตรู่พอ (n +38% WR แทบไม่ลด)
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


def _prev_day_hl(rates, dt_bkk):
    """High/Low ของวันก่อนหน้า (ตามวันที่ของ bar time)"""
    from datetime import datetime
    if dt_bkk is None:
        return None, None
    cur_date = dt_bkk.date()
    prev_h, prev_l, prev_date = None, None, None
    for r in reversed(rates):
        d = datetime.fromtimestamp(int(r["time"])).date()
        if d >= cur_date:
            continue
        if prev_date is None:
            prev_date = d
        if d != prev_date:
            break
        h, l = float(r["high"]), float(r["low"])
        prev_h = h if prev_h is None else max(prev_h, h)
        prev_l = l if prev_l is None else min(prev_l, l)
    return prev_h, prev_l


def _eq_clusters(swings, tol):
    """หา equal highs/lows: swing 2 จุดห่างกัน <= tol -> คืน [(idx_ล่าสุด, price_extreme)]"""
    out = []
    for a in range(len(swings)):
        for b in range(a + 1, len(swings)):
            ia, pa = swings[a]
            ib, pb = swings[b]
            if abs(pa - pb) <= tol:
                out.append((max(ia, ib), max(pa, pb)))
    return out


def detect_s101(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
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

    # เร็วสุดก่อน: displacement ต้องผ่านอย่างน้อยเกณฑ์ stacked
    if d_body < atr * float(c["DISP_BODY_ATR_STACKED"]):
        return {"signal": "WAIT", "reason": "Displacement too small"}

    # --- liquidity pools ---
    all_highs, all_lows = {}, {}
    swings_h_raw, swings_l_raw = [], []
    for left, right in c["SWING_SETS"]:
        hs, ls = _find_swings(rates, int(left), int(right), int(c["SWING_SCAN_BARS"]))
        swings_h_raw += hs
        swings_l_raw += ls
        for idx, price in hs:
            all_highs[idx] = price
        for idx, price in ls:
            all_lows[idx] = price
    if c["USE_EQ_CLUSTERS"]:
        tol = atr * float(c["EQ_TOL_ATR"])
        for idx, price in _eq_clusters(sorted(set(swings_h_raw)), tol):
            all_highs[idx] = max(all_highs.get(idx, price), price)
        for idx, price in _eq_clusters(sorted(set(swings_l_raw)), tol):
            all_lows[idx] = min(all_lows.get(idx, price), price)
    if c["USE_PDH_PDL"]:
        pdh, pdl = _prev_day_hl(rates, dt_bkk)
        # PDH/PDL ให้ index ปลอมที่สดเสมอ (อายุไม่หมด)
        if pdh is not None:
            all_highs[n - 3] = max(all_highs.get(n - 3, pdh), pdh)
        if pdl is not None:
            all_lows[n - 3] = min(all_lows.get(n - 3, pdl), pdl)

    sw_highs = sorted(all_highs.items())
    sw_lows = sorted(all_lows.items())
    max_age = int(c["SWEEP_MAX_AGE"])

    pd_bars = rates[-int(c["PD_RANGE_BARS"]):]
    rng_h = max(float(r["high"]) for r in pd_bars)
    rng_l = min(float(r["low"]) for r in pd_bars)
    eq = (rng_h + rng_l) / 2.0

    closes = [float(r["close"]) for r in rates]
    rsi_sweep = _rsi_at(closes[-81:-1], int(c["RSI_PERIOD"]))

    def _confirm(direction):
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

    def _disp_ok(tags):
        need = float(c["DISP_BODY_ATR_STACKED"]) if len(tags) >= 2 else float(c["DISP_BODY_ATR"])
        return d_body >= atr * need

    def _ml_ok(direction, entry):
        if not c["ML_FILTER_ENABLED"]:
            return True, 1.0
        import ml_scoring
        prob = ml_scoring.score_signal('XAUUSD.iux', tf, direction, entry,
                                       dt_bkk, historical_rates=rates)
        return prob >= float(c["ML_SCORE_THRESHOLD"]), prob

    def _result(direction, entry, sl, tp, swept, tags):
        risk = (entry - sl) if direction == "BUY" else (sl - entry)
        res = {
            "signal": direction,
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "order_type": "limit",
            "pattern": f"S101 HF-Sweep {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
            "reason": (f"Swept {swept[1]:.2f} (age {(n-2)-swept[0]}), "
                       f"disp {d_body:.2f}/{atr:.2f}ATR, confirm: {'+'.join(tags)}"),
            "candles": [sweep_bar, disp_bar],
        }
        if c["TRAIL_ENABLED"]:
            res["trail"] = {
                "be_rr": float(c["TRAIL_BE_RR"]),
                "atr_mult": float(c["TRAIL_ATR_MULT"]),
                "atr": atr,
                "risk": risk,
            }
        return res

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
            if not _disp_ok(tags):
                return {"signal": "WAIT", "reason": "Displacement below adaptive threshold"}
            sweep_ext = max(sw_h, d_h)
            entry = d_c + (sweep_ext - d_c) * float(c["ENTRY_RETRACE"])
            sl = sweep_ext + max(1.5, atr * float(c["SL_BUF_ATR"]))
            risk = sl - entry
            if risk <= 0:
                return {"signal": "WAIT", "reason": "Invalid risk"}
            rr = float(c["TP_RR_MAX"]) if c["TRAIL_ENABLED"] else float(c["TP_RR"])
            tp = entry - risk * rr
            ok, prob = _ml_ok("SELL", entry)
            if not ok:
                return {"signal": "WAIT", "reason": f"S101 SELL blocked by ML ({prob:.2f})"}
            return _result("SELL", entry, sl, tp, swept, tags)

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
            if not _disp_ok(tags):
                return {"signal": "WAIT", "reason": "Displacement below adaptive threshold"}
            sweep_ext = min(sw_l, d_l)
            entry = d_c - (d_c - sweep_ext) * float(c["ENTRY_RETRACE"])
            sl = sweep_ext - max(1.5, atr * float(c["SL_BUF_ATR"]))
            risk = entry - sl
            if risk <= 0:
                return {"signal": "WAIT", "reason": "Invalid risk"}
            rr = float(c["TP_RR_MAX"]) if c["TRAIL_ENABLED"] else float(c["TP_RR"])
            tp = entry + risk * rr
            ok, prob = _ml_ok("BUY", entry)
            if not ok:
                return {"signal": "WAIT", "reason": f"S101 BUY blocked by ML ({prob:.2f})"}
            return _result("BUY", entry, sl, tp, swept, tags)

    return {"signal": "WAIT", "reason": "No sweep+displacement setup"}
