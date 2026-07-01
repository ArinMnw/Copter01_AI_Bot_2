"""
strategy49.py — S49 Session VWAP Bounce, RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด VWAP (Volume Weighted Average Price): institutional algo ส่วนใหญ่อ้างอิง VWAP เป็น
benchmark ราคา "แท้จริง" ของวัน คำนวณใหม่ทุกวัน (reset เที่ยงคืน BKK) จาก cumulative
typical_price x tick_volume / cumulative tick_volume ตั้งแต่เปิดวัน — สร้าง band รอบ VWAP ด้วย
volume-weighted std deviation เข้า BUY ตอนราคาแตะ band ล่างแล้ว reject กลับเข้าหา VWAP, SELL ตอน
แตะ band บนแล้ว reject กลับ — เป็น level-based (เหมือน Volume Profile S44) ที่ session-anchored
(เหมือน ORB S46) ผสมกัน ยืนยันด้วย htf_trend (continuation ไม่ใช่ reversal เต็มรูปแบบ)
"""

S49_DEFAULTS = {
    "ENTRY_TF": "M5",
    "STD_MULT": 1.5,               # band = VWAP ± mult x volume-weighted std
    "TOUCH_ATR_MULT": 0.3,         # ราคาต้องแตะใกล้ band ภายใน mult x ATR
    "REJECT_ATR_MULT": 0.15,       # ต้องปิดถอยห่างจาก band >= mult x ATR (ยืนยัน rejection)
    "MIN_BARS_SINCE_RESET": 12,    # ต้องมีแท่งสะสมอย่างน้อย N แท่งตั้งแต่ reset ถึงคำนวณ VWAP ได้น่าเชื่อ
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
    return S49_DEFAULTS[key]


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


def _session_vwap_band(closed_rates, bar_dt_list, today, std_mult):
    """
    คำนวณ VWAP + volume-weighted std band จากแท่งของ "วันนี้" (reset เที่ยงคืน BKK) เท่านั้น
    คืน (vwap, upper_band, lower_band, n_bars_today) หรือ None ถ้าไม่มีแท่งของวันนี้
    """
    cum_pv = 0.0
    cum_v = 0.0
    today_tp = []
    today_vol = []
    for i, bdt in enumerate(bar_dt_list):
        if bdt is None or bdt.date() != today:
            continue
        r = closed_rates[i]
        tp = (float(r["high"]) + float(r["low"]) + float(r["close"])) / 3.0
        try:
            vol = float(r["tick_volume"]) or 1.0
        except (KeyError, ValueError, IndexError):
            vol = 1.0
        cum_pv += tp * vol
        cum_v += vol
        today_tp.append(tp)
        today_vol.append(vol)
    if cum_v <= 0 or not today_tp:
        return None
    vwap = cum_pv / cum_v
    var = sum(v * (tp - vwap) ** 2 for tp, v in zip(today_tp, today_vol)) / cum_v
    std = var ** 0.5
    upper = vwap + std_mult * std
    lower = vwap - std_mult * std
    return vwap, upper, lower, len(today_tp)


def detect_s49(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None,
               bar_dt_list=None):
    """
    bar_dt_list: list ของ datetime (BKK) คู่กับ closed_rates แต่ละแท่ง (ต้องส่งมาจาก replay เพราะ
    การคำนวณ dt_bkk ทีละแท่งจาก timestamp ต้องใช้ config.mt5_ts_to_bkk ซึ่งอยู่นอกไฟล์นี้)
    """
    if rates is None or len(rates) < 40 or bar_dt_list is None or len(bar_dt_list) != len(rates) - 1:
        return {"signal": "WAIT", "reason": "S49: ข้อมูลไม่พอ"}
    if dt_bkk is None:
        return {"signal": "WAIT", "reason": "S49: ไม่มีเวลา"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S49: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S49: ATR ไม่ได้"}

    today = dt_bkk.date()
    std_mult = float(_cfg(cfg, "STD_MULT"))
    band = _session_vwap_band(closed, bar_dt_list, today, std_mult)
    if band is None:
        return {"signal": "WAIT", "reason": "S49: ไม่มีแท่งของวันนี้"}
    vwap, upper, lower, n_today = band
    if n_today < int(_cfg(cfg, "MIN_BARS_SINCE_RESET")):
        return {"signal": "WAIT", "reason": "S49: แท่งของวันนี้น้อยเกินไป"}

    cur = closed[-1]
    cc = float(cur["close"]); ch = float(cur["high"]); cl = float(cur["low"])
    touch_buf = atr * float(_cfg(cfg, "TOUCH_ATR_MULT"))
    reject_buf = atr * float(_cfg(cfg, "REJECT_ATR_MULT"))

    direction = None
    if cl <= lower + touch_buf and cc >= lower + reject_buf and cc > cl:
        direction = "BUY"
    elif ch >= upper - touch_buf and cc <= upper - reject_buf and cc < ch:
        direction = "SELL"
    if direction is None:
        return {"signal": "WAIT", "reason": "S49: ไม่มี rejection ที่ VWAP band"}

    entry = round(cc, 2)
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    if direction == "BUY":
        sl = round(min(lower, cl) - sl_buf, 2)
    else:
        sl = round(max(upper, ch) + sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S49: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S49: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S49: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S49: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S49: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S49: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 49 VWAP_bounce+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"VWAP={vwap:.2f} band=[{lower:.2f},{upper:.2f}]\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_49(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s49(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None, bar_dt_list=None)
