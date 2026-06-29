"""
strategy51.py — S51 Previous Day High/Low (PDH/PDL) Bounce, RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด PDH/PDL: high/low ของ "เมื่อวาน" (calendar day ก่อนหน้า, reset เที่ยงคืน BKK) เป็นแนวรับ/
แนวต้านที่ traders จับตาดูเสมอ (classic structural level) — ต่างจาก S37 (fractal pivot จาก
intrabar M5) ตรงที่ใช้ daily OHLC โดยตรง ไม่ต้องหา pivot แบบ fractal — เข้า BUY ตอนราคาแตะ PDL
แล้ว reject กลับขึ้น, SELL ตอนแตะ PDH แล้ว reject กลับลง ยืนยันด้วย htf_trend (continuation)
"""

S51_DEFAULTS = {
    "ENTRY_TF": "M5",
    "TOUCH_ATR_MULT": 0.3,         # ราคาต้องแตะใกล้ PDH/PDL ภายใน mult x ATR
    "REJECT_ATR_MULT": 0.15,       # ต้องปิดถอยห่างจาก PDH/PDL >= mult x ATR (ยืนยัน rejection)
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
    return S51_DEFAULTS[key]


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


def _prev_day_high_low(closed_rates, bar_dt_list, today):
    """หา high/low ของวันก่อนหน้า (calendar day, BKK) ที่มีแท่งครบ — คืน (pdh, pdl) หรือ None"""
    from datetime import timedelta
    yesterday = today - timedelta(days=1)
    highs, lows = [], []
    for i, bdt in enumerate(bar_dt_list):
        if bdt is None:
            continue
        if bdt.date() == yesterday:
            highs.append(float(closed_rates[i]["high"]))
            lows.append(float(closed_rates[i]["low"]))
    if not highs:
        return None
    return max(highs), min(lows)


def detect_s51(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None,
               bar_dt_list=None):
    """
    bar_dt_list: list ของ datetime (BKK) คู่กับ closed_rates แต่ละแท่ง (ต้องส่งมาจาก replay เพราะ
    การคำนวณ dt_bkk ทีละแท่งจาก timestamp ต้องใช้ config.mt5_ts_to_bkk ซึ่งอยู่นอกไฟล์นี้)
    """
    if rates is None or len(rates) < 40 or bar_dt_list is None or len(bar_dt_list) != len(rates) - 1:
        return {"signal": "WAIT", "reason": "S51: ข้อมูลไม่พอ"}
    if dt_bkk is None:
        return {"signal": "WAIT", "reason": "S51: ไม่มีเวลา"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S51: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S51: ATR ไม่ได้"}

    today = dt_bkk.date()
    pd_levels = _prev_day_high_low(closed, bar_dt_list, today)
    if pd_levels is None:
        return {"signal": "WAIT", "reason": "S51: ไม่มีข้อมูลเมื่อวาน"}
    pdh, pdl = pd_levels

    cur = closed[-1]
    cc = float(cur["close"]); ch = float(cur["high"]); cl = float(cur["low"])
    touch_buf = atr * float(_cfg(cfg, "TOUCH_ATR_MULT"))
    reject_buf = atr * float(_cfg(cfg, "REJECT_ATR_MULT"))

    direction = None
    level_hit = None
    if cl <= pdl + touch_buf and cc >= pdl + reject_buf and cc > cl:
        direction = "BUY"; level_hit = pdl
    elif ch >= pdh - touch_buf and cc <= pdh - reject_buf and cc < ch:
        direction = "SELL"; level_hit = pdh
    if direction is None:
        return {"signal": "WAIT", "reason": "S51: ไม่มี rejection ที่ PDH/PDL"}

    entry = round(cc, 2)
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    if direction == "BUY":
        sl = round(min(level_hit, cl) - sl_buf, 2)
    else:
        sl = round(max(level_hit, ch) + sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S51: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S51: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S51: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S51: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S51: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S51: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 51 PDH_PDL+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"PDH/PDL=[{pdl:.2f},{pdh:.2f}] level={level_hit:.2f}\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }
