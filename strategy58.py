"""
strategy58.py — S58 Weekly-Open Reaction Bounce, RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด: "weekly open" (ราคาเปิดของสัปดาห์ปัจจุบัน, open ของ W1 bar ปัจจุบัน) เป็นระดับอ้างอิงกลาง
ที่ institutional ใช้เป็น benchmark ทั้งสัปดาห์ — เป็น **endogenous level** (ราคาที่เทรดจริง ณ จุด
เปิดสัปดาห์) ต่างจาก S56 (weekly H/L extremes) ตรงที่เป็นระดับ "กลาง" ไม่ใช่ขอบ จึง decorrelate

เป็น single level ที่ทำหน้าที่ทั้งแนวรับและแนวต้านขึ้นกับว่าราคาเข้าหาจากด้านไหน: ราคากลับมาแตะ
weekly open จากด้านบนแล้ว reject ขึ้น (open = support) -> BUY, จากด้านล่างแล้ว reject ลง
(open = resistance) -> SELL — mean-reversion กลับเข้าหา anchor กลางสัปดาห์
"""

S58_DEFAULTS = {
    "ENTRY_TF": "M5",
    "TOUCH_ATR_MULT": 0.3,         # ราคาต้องแตะใกล้ระดับภายใน mult x ATR
    "REJECT_ATR_MULT": 0.15,       # ต้องปิดถอยห่างจากระดับ >= mult x ATR (ยืนยัน rejection)
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
    return S58_DEFAULTS[key]


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


def detect_s58(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None,
               week_open=None):
    """
    week_open: float = ราคาเปิดของสัปดาห์ปัจจุบัน (ต้องส่งมาจาก replay เพราะคำนวณจาก W1 bars
    ซึ่งอยู่นอกไฟล์นี้)
    """
    if rates is None or len(rates) < 30:
        return {"signal": "WAIT", "reason": "S58: ข้อมูลไม่พอ"}
    if week_open is None:
        return {"signal": "WAIT", "reason": "S58: ไม่มี weekly open"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S58: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S58: ATR ไม่ได้"}

    wopen = float(week_open)
    if wopen <= 0:
        return {"signal": "WAIT", "reason": "S58: weekly open ผิด"}

    cur = closed[-1]
    co = float(cur["open"]); cc = float(cur["close"]); ch = float(cur["high"]); cl = float(cur["low"])
    touch_buf = atr * float(_cfg(cfg, "TOUCH_ATR_MULT"))
    reject_buf = atr * float(_cfg(cfg, "REJECT_ATR_MULT"))

    direction = None
    level_hit = wopen
    # เข้าหา weekly open จากด้านบน (เปิดเหนือ open) แล้วแตะ + reject ขึ้น -> BUY (open=support)
    if co >= wopen and cl <= wopen + touch_buf and cc >= wopen + reject_buf and cc > cl:
        direction = "BUY"
    # เข้าหา weekly open จากด้านล่าง (เปิดใต้ open) แล้วแตะ + reject ลง -> SELL (open=resistance)
    elif co <= wopen and ch >= wopen - touch_buf and cc <= wopen - reject_buf and cc < ch:
        direction = "SELL"
    if direction is None:
        return {"signal": "WAIT", "reason": "S58: ไม่มี reaction ที่ weekly open"}

    entry = round(cc, 2)
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    if direction == "BUY":
        sl = round(min(level_hit, cl) - sl_buf, 2)
    else:
        sl = round(max(level_hit, ch) + sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S58: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S58: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S58: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S58: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S58: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S58: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 58 WeekOpen+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"WeekOpen={wopen:.2f}\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }
