"""
strategy45.py — S45 Order Block (SMC) — last-candle-before-impulse zone, RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด ICT/SMC Order Block: **bullish OB** = แท่งแดงล่าสุด (close<open) ก่อนแท่ง/กลุ่มแท่งที่วิ่ง
ขึ้นแรง (impulse, range >= IMPULSE_ATR_MULT x ATR ทะลุ high ของแท่งแดงนั้น) — โซน [low,high] ของ
แท่งแดงนั้นกลายเป็น "order block" (จุดที่ smart money สั่งซื้อก่อนดันราคาขึ้น) **bearish OB** =
แท่งเขียวล่าสุดก่อน impulse ลง — ต่างจาก S39 (Demand/Supply) ที่ใช้ "โซน consolidation หลายแท่ง"
ส่วน Order Block ใช้ **แท่งเดียว** (last opposite-color candle) เป็นนิยามที่เข้มงวดกว่า/แคบกว่า
"""

S45_DEFAULTS = {
    "ENTRY_TF": "M5",
    "IMPULSE_ATR_MULT": 1.0,       # แท่ง impulse ต้องมี range >= mult x ATR
    "MAX_OB_AGE_BARS": 40,         # OB ต้องเกิดภายใน N แท่งล่าสุด
    "MAX_VIOLATION_WICK_ATR": 0.1, # อนุโลม wick ทะลุ OB ได้เล็กน้อย (mult x ATR) ก่อนถือว่า invalidate
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
    return S45_DEFAULTS[key]


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


def _find_order_block(closed_rates, atr, cfg):
    """
    หา order block ล่าสุดที่ยังไม่ถูก invalidate — สแกนถอยหลังหาแท่ง impulse แล้วเช็คแท่งก่อนหน้า
    (สีตรงข้าม) เป็น OB candidate
    คืน (direction, ob_high, ob_low, ob_idx) หรือ None
    """
    impulse_mult = float(_cfg(cfg, "IMPULSE_ATR_MULT"))
    max_age = int(_cfg(cfg, "MAX_OB_AGE_BARS"))
    violation_buf = float(_cfg(cfg, "MAX_VIOLATION_WICK_ATR")) * atr
    n = len(closed_rates)
    earliest = max(1, n - max_age - 1)

    for i in range(n - 1, earliest - 1, -1):
        imp = closed_rates[i]
        imp_o = float(imp["open"]); imp_c = float(imp["close"])
        imp_range = float(imp["high"]) - float(imp["low"])
        if imp_range < impulse_mult * atr:
            continue
        prev = closed_rates[i - 1]
        prev_o = float(prev["open"]); prev_c = float(prev["close"])
        ob_high = float(prev["high"]); ob_low = float(prev["low"])

        is_bull_ob = imp_c > imp_o and prev_c < prev_o and float(imp["close"]) > ob_high
        is_bear_ob = imp_c < imp_o and prev_c > prev_o and float(imp["close"]) < ob_low
        if not (is_bull_ob or is_bear_ob):
            continue

        direction = "BUY" if is_bull_ob else "SELL"
        violated = False
        for k in range(i + 1, n):
            c = closed_rates[k]
            if direction == "BUY" and float(c["close"]) < ob_low - violation_buf:
                violated = True; break
            if direction == "SELL" and float(c["close"]) > ob_high + violation_buf:
                violated = True; break
        if violated:
            continue
        return (direction, ob_high, ob_low, i - 1)
    return None


def detect_s45(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    max_age = int(_cfg(cfg, "MAX_OB_AGE_BARS"))
    need = max_age + 30
    if rates is None or len(rates) < min(need, 50):
        return {"signal": "WAIT", "reason": "S45: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S45: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S45: ATR ไม่ได้"}

    ob = _find_order_block(closed, atr, cfg)
    if ob is None:
        return {"signal": "WAIT", "reason": "S45: ไม่พบ order block ที่ยังไม่ invalidate"}
    direction, ob_high, ob_low, _ = ob

    cur = closed[-1]
    cc = float(cur["close"])

    if direction == "BUY":
        if not (ob_low <= cc <= ob_high):
            return {"signal": "WAIT", "reason": "S45: ราคายังไม่ย้อนกลับเข้า bullish OB"}
        entry = round(cc, 2)
        sl = round(ob_low - float(_cfg(cfg, "SL_ATR_MULT")) * atr, 2)
    else:
        if not (ob_low <= cc <= ob_high):
            return {"signal": "WAIT", "reason": "S45: ราคายังไม่ย้อนกลับเข้า bearish OB"}
        entry = round(cc, 2)
        sl = round(ob_high + float(_cfg(cfg, "SL_ATR_MULT")) * atr, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S45: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S45: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S45: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S45: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S45: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S45: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 45 OrderBlock+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"OB=[{ob_low:.2f},{ob_high:.2f}]\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_45(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s45(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
