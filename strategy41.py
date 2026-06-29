"""
strategy41.py — S41 RSI Divergence (price/momentum divergence, reversal), RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live
(แยกจาก strategy9.py เดิมที่ใช้ RSI divergence อยู่แล้วใน live bot S1-S20 — ไฟล์นี้คือ research ใหม่
ในเฟรมเวิร์ก S30+)

แนวคิด: หา fractal pivot low/high 2 จุดล่าสุด (เหมือน S37) พร้อมค่า RSI(14) ที่จุดนั้น —
**bullish divergence**: price ทำ lower-low แต่ RSI ทำ higher-low (momentum ขาลงอ่อนกำลัง) → คาดหวัง
reversal ขึ้น เข้า BUY ตอนราคา confirm กลับขึ้น **bearish divergence**: price ทำ higher-high แต่
RSI ทำ lower-high → เข้า SELL — เป็น reversal pattern (ไม่ใช่ continuation เหมือน A/D/E/F) จึง
ไม่ใช้ htf_trend filter โดย default (เหมือน S35) แต่ทดสอบทั้งสองแบบใน grid search
"""

S41_DEFAULTS = {
    "ENTRY_TF": "M5",
    "PIVOT_WING": 3,               # fractal pivot wing เหมือน S37
    "MAX_LEVEL_AGE_BARS": 80,       # หา pivot ย้อนหลัง N แท่ง
    "RSI_PERIOD": 14,
    "MIN_PRICE_DIFF_ATR": 0.3,      # pivot 2 จุดต้องต่างราคากัน >= mult x ATR (กัน noise)
    "MIN_RSI_DIFF": 3.0,            # RSI ที่ 2 pivot ต้องต่างกัน >= ค่านี้ (ยืนยัน divergence จริง)
    "MAX_CONFIRM_AGE_BARS": 10,     # ต้อง confirm reversal ภายใน N แท่งหลัง pivot ล่าสุด
    "SL_ATR_MULT": 1.0,
    "TP_RR": 1.2,
    "MAX_RISK_ATR_MULT": 5.0,
    "MIN_GAP_BARS": 1,
    "SESSION_FILTER": True,
    "SESSIONS": [("14:00", "23:00")],

    "RISK_PCT": 0.5,
    "DD_CONTROL": "circuit_breaker",
    "CONSEC_LOSS_TRIGGER": 3,
    "REDUCED_RISK_PCT": 0.4,
    "COOLDOWN_TRADES": 10,

    "CONFIRMATION_TYPE": "none",
    "HTF_TF": "M15",
    "HTF_EMA_PERIOD": 50,
    "HTF_SLOPE_BARS": 5,
    "ADX_PERIOD": 14,
    "ADX_MIN_THRESHOLD": 0.0,
}


def _cfg(cfg, key):
    if cfg and key in cfg:
        return cfg[key]
    return S41_DEFAULTS[key]


def _calc_atr(rates, period=14):
    n = len(rates)
    if n == 0:
        return 0.0
    trs = []
    for i in range(n):
        h = float(rates[i]["high"]); l = float(rates[i]["low"])
        if i == 0:
            trs.append(h - l)
        else:
            pc = float(rates[i - 1]["close"])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return sum(trs) / len(trs) if trs else 0.0
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return atr


def _calc_rsi_series(rates, period=14):
    n = len(rates)
    closes = [float(r["close"]) for r in rates]
    rsi = [50.0] * n
    if n < period + 1:
        return rsi
    gains, losses = [], []
    for i in range(1, n):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        idx = i + 1
        if avg_loss == 0:
            rsi[idx] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[idx] = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def _in_session(dt_bkk, cfg):
    if not _cfg(cfg, "SESSION_FILTER"):
        return True
    if dt_bkk is None:
        return True
    from datetime import time
    cur = dt_bkk.time()
    for start_str, end_str in _cfg(cfg, "SESSIONS"):
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        if time(sh, sm) <= cur < time(eh, em):
            return True
    return False


def _find_pivots_with_rsi(closed_rates, rsi_series, cfg):
    wing = int(_cfg(cfg, "PIVOT_WING"))
    max_age = int(_cfg(cfg, "MAX_LEVEL_AGE_BARS"))
    n = len(closed_rates)
    start = max(wing, n - max_age)
    res_pivots, sup_pivots = [], []
    for i in range(start, n - wing):
        h = float(closed_rates[i]["high"]); l = float(closed_rates[i]["low"])
        is_res = all(h > float(closed_rates[i - k]["high"]) and h > float(closed_rates[i + k]["high"])
                     for k in range(1, wing + 1))
        is_sup = all(l < float(closed_rates[i - k]["low"]) and l < float(closed_rates[i + k]["low"])
                     for k in range(1, wing + 1))
        if is_res:
            res_pivots.append((i, h, rsi_series[i]))
        if is_sup:
            sup_pivots.append((i, l, rsi_series[i]))
    return res_pivots, sup_pivots


def detect_s41(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    wing = int(_cfg(cfg, "PIVOT_WING"))
    need = int(_cfg(cfg, "MAX_LEVEL_AGE_BARS")) + wing * 2 + 30
    if rates is None or len(rates) < min(need, 80):
        return {"signal": "WAIT", "reason": "S41: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S41: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S41: ATR ไม่ได้"}

    rsi_period = int(_cfg(cfg, "RSI_PERIOD"))
    rsi_series = _calc_rsi_series(closed, rsi_period)

    pivot_rates = closed[:-wing] if wing > 0 else closed
    pivot_rsi = rsi_series[:len(pivot_rates)]
    res_pivots, sup_pivots = _find_pivots_with_rsi(pivot_rates, pivot_rsi, cfg)

    cur = closed[-1]
    cc = float(cur["close"])
    min_price_diff = float(_cfg(cfg, "MIN_PRICE_DIFF_ATR")) * atr
    min_rsi_diff = float(_cfg(cfg, "MIN_RSI_DIFF"))
    max_confirm_age = int(_cfg(cfg, "MAX_CONFIRM_AGE_BARS"))

    direction = None
    last_idx = len(closed) - 1

    if len(sup_pivots) >= 2:
        p1, p2 = sup_pivots[-2], sup_pivots[-1]
        idx2, price2, rsi2 = p2
        idx1, price1, rsi1 = p1
        if (price1 - price2) >= min_price_diff and (rsi2 - rsi1) >= min_rsi_diff:
            age = last_idx - idx2
            if age <= max_confirm_age and cc > price2 and cc > float(closed[last_idx - 1]["close"] if last_idx > 0 else cc):
                direction = "BUY"
                ref_low = min(price1, price2)

    if direction is None and len(res_pivots) >= 2:
        p1, p2 = res_pivots[-2], res_pivots[-1]
        idx2, price2, rsi2 = p2
        idx1, price1, rsi1 = p1
        if (price2 - price1) >= min_price_diff and (rsi1 - rsi2) >= min_rsi_diff:
            age = last_idx - idx2
            if age <= max_confirm_age and cc < price2 and cc < float(closed[last_idx - 1]["close"] if last_idx > 0 else cc):
                direction = "SELL"
                ref_high = max(price1, price2)

    if direction is None:
        return {"signal": "WAIT", "reason": "S41: ไม่พบ RSI divergence ที่ยืนยันแล้ว"}

    entry = round(cc, 2)
    sl_buf = float(_cfg(cfg, "SL_ATR_MULT")) * atr
    if direction == "BUY":
        sl = round(ref_low - sl_buf, 2)
    else:
        sl = round(ref_high + sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S41: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S41: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S41: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S41: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S41: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S41: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 41 RSI_divergence+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"RSI divergence confirm\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_41(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s41(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
