"""
strategy54.py — S54 Floor Trader Pivot Points Bounce, RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด Floor Trader Pivot Points (quant model มาตรฐานที่ใช้กันมานานในเทรดดิ้งเดสก์): คำนวณจาก
high/low/close ของ "เมื่อวาน" (calendar day, reset เที่ยงคืน BKK) ด้วยสูตรตายตัว:
PP = (H+L+C)/3, R1 = 2*PP-L, S1 = 2*PP-H, R2 = PP+(H-L), S2 = PP-(H-L) — ต่างจาก S51 (PDH/PDL
ตรงๆ) เพราะ S54 สร้างระดับสังเคราะห์เพิ่ม (PP, R1, R2, S1, S2) ที่ไม่ใช่ high/low ดิบ แต่มาจาก
สูตรคณิตศาสตร์ — เข้า BUY ตอนราคาแตะระดับ support (S1/S2/PP จากด้านบน) แล้ว reject กลับขึ้น, SELL
ตอนแตะระดับ resistance (R1/R2/PP จากด้านล่าง) แล้ว reject กลับลง ยืนยันด้วย htf_trend
"""

S54_DEFAULTS = {
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
    return S54_DEFAULTS[key]


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


def _prev_day_pivots(closed_rates, bar_dt_list, today):
    """
    หา H/L/C ของวันก่อนหน้า (calendar day, BKK) แล้วคำนวณ floor pivot points มาตรฐาน
    คืน dict {pp, r1, r2, s1, s2} หรือ None
    """
    from datetime import timedelta
    yesterday = today - timedelta(days=1)
    highs, lows, closes_with_time = [], [], []
    for i, bdt in enumerate(bar_dt_list):
        if bdt is None:
            continue
        if bdt.date() == yesterday:
            highs.append(float(closed_rates[i]["high"]))
            lows.append(float(closed_rates[i]["low"]))
            closes_with_time.append((bdt, float(closed_rates[i]["close"])))
    if not highs:
        return None
    h = max(highs); l = min(lows)
    c = max(closes_with_time, key=lambda x: x[0])[1]  # close ของแท่งสุดท้ายของวันก่อนหน้า
    pp = (h + l + c) / 3.0
    r1 = 2 * pp - l
    s1 = 2 * pp - h
    r2 = pp + (h - l)
    s2 = pp - (h - l)
    return {"pp": pp, "r1": r1, "r2": r2, "s1": s1, "s2": s2}


def detect_s54(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None,
               bar_dt_list=None):
    """
    bar_dt_list: list ของ datetime (BKK) คู่กับ closed_rates แต่ละแท่ง (ต้องส่งมาจาก replay เพราะ
    การคำนวณ dt_bkk ทีละแท่งจาก timestamp ต้องใช้ config.mt5_ts_to_bkk ซึ่งอยู่นอกไฟล์นี้)
    """
    if rates is None or len(rates) < 40 or bar_dt_list is None or len(bar_dt_list) != len(rates) - 1:
        return {"signal": "WAIT", "reason": "S54: ข้อมูลไม่พอ"}
    if dt_bkk is None:
        return {"signal": "WAIT", "reason": "S54: ไม่มีเวลา"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S54: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S54: ATR ไม่ได้"}

    today = dt_bkk.date()
    pivots = _prev_day_pivots(closed, bar_dt_list, today)
    if pivots is None:
        return {"signal": "WAIT", "reason": "S54: ไม่มีข้อมูลเมื่อวาน"}

    support_levels = [pivots["s1"], pivots["s2"], pivots["pp"]]
    resistance_levels = [pivots["r1"], pivots["r2"], pivots["pp"]]

    cur = closed[-1]
    cc = float(cur["close"]); ch = float(cur["high"]); cl = float(cur["low"])
    touch_buf = atr * float(_cfg(cfg, "TOUCH_ATR_MULT"))
    reject_buf = atr * float(_cfg(cfg, "REJECT_ATR_MULT"))

    direction = None
    level_hit = None
    for lvl in support_levels:
        if cl <= lvl + touch_buf and cc >= lvl + reject_buf and cc > cl:
            direction = "BUY"; level_hit = lvl
            break
    if direction is None:
        for lvl in resistance_levels:
            if ch >= lvl - touch_buf and cc <= lvl - reject_buf and cc < ch:
                direction = "SELL"; level_hit = lvl
                break
    if direction is None:
        return {"signal": "WAIT", "reason": "S54: ไม่มี rejection ที่ pivot level"}

    entry = round(cc, 2)
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    if direction == "BUY":
        sl = round(min(level_hit, cl) - sl_buf, 2)
    else:
        sl = round(max(level_hit, ch) + sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S54: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S54: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S54: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S54: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S54: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S54: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 54 FloorPivot+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"PP={pivots['pp']:.2f} level={level_hit:.2f}\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }
