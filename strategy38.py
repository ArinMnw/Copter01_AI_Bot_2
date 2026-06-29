"""
strategy38.py — S38 Fibonacci Premium/Discount (OTE — Optimal Trade Entry), RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด ICT: หา swing impulse ล่าสุด (high/low สุดขั้วใน SWING_LOOKBACK_BARS แท่ง) ถ้า low เกิดก่อน
high = impulse ขาขึ้น (bullish) → รอราคาย้อนกลับเข้าโซน "discount" (fib retrace 61.8%-78.6% จาก high)
แล้วเข้า BUY ต่อทิศเดิม. ถ้า high เกิดก่อน low = impulse ขาลง (bearish) → รอราคาย้อนขึ้นเข้าโซน
"premium" (fib retrace 61.8%-78.6% จาก low) แล้วเข้า SELL ต่อทิศเดิม — ยืนยันด้วย htf_trend
(M15/EMA50) เหมือน A/B/C/D
"""

S38_DEFAULTS = {
    "ENTRY_TF": "M5",
    "SWING_LOOKBACK_BARS": 40,     # หา swing high/low สุดขั้วใน N แท่งล่าสุด
    "MIN_SWING_ATR": 3.0,          # swing range ต้อง >= mult x ATR (กัน impulse เล็กเกินไป/noise)
    "OTE_LOW": 0.618,              # ขอบโซน OTE (fib retrace pct)
    "OTE_HIGH": 0.786,
    "MAX_RETRACE_AGE_BARS": 20,    # ราคาต้องย้อนเข้าโซนภายใน N แท่งหลัง extreme ล่าสุด
    "SL_ATR_MULT": 1.0,
    "TP_RR": 1.5,
    "MAX_RISK_ATR_MULT": 5.0,
    "MIN_GAP_BARS": 1,
    "SESSION_FILTER": True,
    "SESSIONS": [("14:00", "23:00")],

    "RISK_PCT": 0.5,
    "DD_CONTROL": "circuit_breaker",
    "CONSEC_LOSS_TRIGGER": 3,
    "REDUCED_RISK_PCT": 0.4,
    "COOLDOWN_TRADES": 10,

    "CONFIRMATION_TYPE": "htf_trend",
    "HTF_TF": "M15",
    "HTF_EMA_PERIOD": 50,
    "HTF_SLOPE_BARS": 5,
    "ADX_PERIOD": 14,
    "ADX_MIN_THRESHOLD": 0.0,
}


def _cfg(cfg, key):
    if cfg and key in cfg:
        return cfg[key]
    return S38_DEFAULTS[key]


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


def _find_swing_impulse(closed_rates, atr, cfg):
    """
    หา extreme high/low ใน SWING_LOOKBACK_BARS แท่งล่าสุด (ไม่รวมแท่งปัจจุบัน) แล้วดูว่า
    extreme ไหนเกิดทีหลัง (อายุน้อยกว่า) เพื่อกำหนดทิศ impulse
    คืน (direction, swing_high, swing_low, age_of_last_extreme) หรือ None
    """
    lb = int(_cfg(cfg, "SWING_LOOKBACK_BARS"))
    n = len(closed_rates)
    start = max(0, n - lb)
    window = closed_rates[start:n]
    if len(window) < 5:
        return None

    hi_idx, hi_val = max(enumerate(window), key=lambda kv: float(kv[1]["high"]))
    lo_idx, lo_val = min(enumerate(window), key=lambda kv: float(kv[1]["low"]))
    swing_high = float(hi_val["high"])
    swing_low = float(lo_val["low"])
    swing_range = swing_high - swing_low
    if swing_range < float(_cfg(cfg, "MIN_SWING_ATR")) * atr:
        return None

    last_idx = len(window) - 1
    if lo_idx < hi_idx:
        direction = "BUY"
        age = last_idx - hi_idx
    elif hi_idx < lo_idx:
        direction = "SELL"
        age = last_idx - lo_idx
    else:
        return None
    return (direction, swing_high, swing_low, age)


def detect_s38(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    lb = int(_cfg(cfg, "SWING_LOOKBACK_BARS"))
    need = lb + 20
    if rates is None or len(rates) < need:
        return {"signal": "WAIT", "reason": f"S38: ข้อมูลไม่พอ (>= {need})"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S38: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S38: ATR ไม่ได้"}

    swing = _find_swing_impulse(closed, atr, cfg)
    if swing is None:
        return {"signal": "WAIT", "reason": "S38: ไม่พบ swing impulse ที่ใหญ่พอ"}
    direction, swing_high, swing_low, age = swing
    if age > int(_cfg(cfg, "MAX_RETRACE_AGE_BARS")):
        return {"signal": "WAIT", "reason": "S38: swing เก่าเกินไป"}

    rng = swing_high - swing_low
    ote_low_pct = float(_cfg(cfg, "OTE_LOW"))
    ote_high_pct = float(_cfg(cfg, "OTE_HIGH"))
    cur = closed[-1]
    cc = float(cur["close"])

    if direction == "BUY":
        zone_lo = swing_low + (1 - ote_high_pct) * rng
        zone_hi = swing_low + (1 - ote_low_pct) * rng
        if not (zone_lo <= cc <= zone_hi):
            return {"signal": "WAIT", "reason": "S38: ราคายังไม่เข้าโซน discount (OTE)"}
        entry = round(cc, 2)
        sl = round(swing_low - float(_cfg(cfg, "SL_ATR_MULT")) * atr, 2)
    else:
        zone_lo = swing_low + ote_low_pct * rng
        zone_hi = swing_low + ote_high_pct * rng
        if not (zone_lo <= cc <= zone_hi):
            return {"signal": "WAIT", "reason": "S38: ราคายังไม่เข้าโซน premium (OTE)"}
        entry = round(cc, 2)
        sl = round(swing_high + float(_cfg(cfg, "SL_ATR_MULT")) * atr, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S38: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S38: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S38: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S38: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S38: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S38: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 38 Fibo_OTE+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"OTE zone swing=[{swing_low:.2f},{swing_high:.2f}]\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_38(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s38(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
