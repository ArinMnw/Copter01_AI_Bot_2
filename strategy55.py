"""
strategy55.py — S55 Round-Number Psychological Level Bounce, RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด: ทอง (XAUUSD) เคารพ "เลขกลม" (round number) อย่างมาก เพราะ institutional order กระจุกตัวที่
ระดับราคาที่เป็นเลขลงตัว ($X00.00 เต็มร้อย แรงสุด, $X50.00 ครึ่งร้อย, $X0.00 สิบ) — ระดับเหล่านี้
**ไม่ได้มาจาก price action/volume/session/OHLC เดิมเลย** แต่มาจากจิตวิทยามนุษย์ล้วนๆ จึง decorrelate
กับทุก leg ที่มีอยู่โดยโครงสร้าง

ROUND_STEP กำหนดระยะห่างของ grid เลขกลม (เช่น 50 = ทุก $50, 25 = ทุก $25, 10 = ทุก $10) หา
ระดับเลขกลมที่ใกล้ราคาปัจจุบันที่สุด (บน=resistance, ล่าง=support) เข้า BUY เมื่อราคาแตะระดับล่าง
แล้ว reject กลับขึ้น, SELL เมื่อแตะระดับบนแล้ว reject กลับลง ต่อทิศ htf_trend — กลไก rejection
เดียวกับ S37/S44/S49/S51 แต่ระดับมาจากเลขกลม
"""

S55_DEFAULTS = {
    "ENTRY_TF": "M5",
    "ROUND_STEP": 50.0,            # ระยะห่าง grid เลขกลม (dollar) — 50 = ทุก $50
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
    return S55_DEFAULTS[key]


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


def detect_s55(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    if rates is None or len(rates) < 30:
        return {"signal": "WAIT", "reason": "S55: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S55: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S55: ATR ไม่ได้"}

    step = float(_cfg(cfg, "ROUND_STEP"))
    if step <= 0:
        return {"signal": "WAIT", "reason": "S55: ROUND_STEP ผิด"}

    cur = closed[-1]
    cc = float(cur["close"]); ch = float(cur["high"]); cl = float(cur["low"])

    # ระดับเลขกลมที่ครอบราคาปัจจุบัน: ล่าง (support) และ บน (resistance)
    import math
    round_below = math.floor(cc / step) * step
    round_above = math.ceil(cc / step) * step
    if round_above == round_below:  # ราคาตรงเลขกลมพอดี
        round_above = round_below + step

    touch_buf = atr * float(_cfg(cfg, "TOUCH_ATR_MULT"))
    reject_buf = atr * float(_cfg(cfg, "REJECT_ATR_MULT"))

    direction = None
    level_hit = None
    # แตะระดับล่าง (support) แล้ว reject ขึ้น -> BUY
    if cl <= round_below + touch_buf and cc >= round_below + reject_buf and cc > cl:
        direction = "BUY"; level_hit = round_below
    # แตะระดับบน (resistance) แล้ว reject ลง -> SELL
    elif ch >= round_above - touch_buf and cc <= round_above - reject_buf and cc < ch:
        direction = "SELL"; level_hit = round_above
    if direction is None:
        return {"signal": "WAIT", "reason": "S55: ไม่มี rejection ที่เลขกลม"}

    entry = round(cc, 2)
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    if direction == "BUY":
        sl = round(min(level_hit, cl) - sl_buf, 2)
    else:
        sl = round(max(level_hit, ch) + sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S55: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S55: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S55: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S55: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S55: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S55: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 55 RoundNumber+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"Round level={level_hit:.2f} (step={step})\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_55(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s55(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
