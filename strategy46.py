"""
strategy46.py — S46 Opening Range Breakout (ORB), RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด ORB: นิยาม "opening range" = high/low ของแท่งในช่วง OR_MINUTES นาทีแรกหลัง session เปิด
(ค่าเริ่มต้น = London open 14:00 BKK) ตามด้วยรอ breakout เลยขอบ range ในช่วงที่เหลือของ session
(BUY เมื่อทะลุ OR high, SELL เมื่อทะลุ OR low) — เหมือน Donchian breakout (S43, ตกแล้ว) แต่ใช้
session-anchored range แทน rolling window อาจมี edge ต่างกันเพราะ session open มักมี volatility
expansion ที่แตกต่างจาก breakout เวลาอื่น
"""

S46_DEFAULTS = {
    "ENTRY_TF": "M5",
    "OR_SESSION_START": "14:00",   # เวลาเปิด session (BKK) — London open
    "OR_MINUTES": 30,              # ความยาวของ opening range (นาที)
    "MAX_BREAKOUT_AGE_MIN": 180,   # breakout ต้องเกิดภายใน N นาทีหลัง OR ปิด
    "MIN_BREAK_ATR": 0.1,          # ต้อง break เลยขอบ range >= mult x ATR
    "SL_ATR_MULT": 1.0,
    "TP_RR": 1.5,
    "MAX_RISK_ATR_MULT": 5.0,
    "MIN_GAP_BARS": 1,

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
    return S46_DEFAULTS[key]


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


def detect_s46(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None,
               bar_dt_list=None):
    """
    bar_dt_list: list ของ datetime (BKK) คู่กับ closed_rates แต่ละแท่ง (ต้องส่งมาจาก replay เพราะ
    การคำนวณ dt_bkk ทีละแท่งจาก timestamp ต้องใช้ config.mt5_ts_to_bkk ซึ่งอยู่นอกไฟล์นี้)
    """
    if rates is None or len(rates) < 40 or bar_dt_list is None or len(bar_dt_list) != len(rates) - 1:
        return {"signal": "WAIT", "reason": "S46: ข้อมูลไม่พอ"}
    if dt_bkk is None:
        return {"signal": "WAIT", "reason": "S46: ไม่มีเวลา"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S46: ATR ไม่ได้"}

    from datetime import datetime, time as dtime, timedelta
    sh, sm = map(int, _cfg(cfg, "OR_SESSION_START").split(":"))
    or_minutes = int(_cfg(cfg, "OR_MINUTES"))
    max_age_min = int(_cfg(cfg, "MAX_BREAKOUT_AGE_MIN"))

    today = dt_bkk.date()
    session_open_dt = datetime.combine(today, dtime(sh, sm), tzinfo=dt_bkk.tzinfo)
    or_close_dt = session_open_dt + timedelta(minutes=or_minutes)
    breakout_deadline = or_close_dt + timedelta(minutes=max_age_min)

    if dt_bkk <= or_close_dt or dt_bkk > breakout_deadline:
        return {"signal": "WAIT", "reason": "S46: นอกช่วง breakout window ของวันนี้"}

    or_highs, or_lows = [], []
    for i, bdt in enumerate(bar_dt_list):
        if bdt is None:
            continue
        if bdt.date() == today and session_open_dt <= bdt < or_close_dt:
            or_highs.append(float(closed[i]["high"]))
            or_lows.append(float(closed[i]["low"]))
    if not or_highs:
        return {"signal": "WAIT", "reason": "S46: ไม่มีแท่งใน opening range ของวันนี้"}

    or_high = max(or_highs)
    or_low = min(or_lows)
    sig_bar = closed[-1]
    sc = float(sig_bar["close"])
    break_buf = float(_cfg(cfg, "MIN_BREAK_ATR")) * atr

    direction = None
    if sc >= or_high + break_buf:
        direction = "BUY"
    elif sc <= or_low - break_buf:
        direction = "SELL"
    if direction is None:
        return {"signal": "WAIT", "reason": "S46: ไม่มี ORB breakout"}

    entry = round(sc, 2)
    sl_buf = float(_cfg(cfg, "SL_ATR_MULT")) * atr
    if direction == "BUY":
        sl = round(or_low - sl_buf, 2)
    else:
        sl = round(or_high + sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S46: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S46: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S46: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S46: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S46: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S46: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 46 ORB+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"ORB range=[{or_low:.2f},{or_high:.2f}]\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }
