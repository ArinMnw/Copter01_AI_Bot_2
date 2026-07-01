"""
strategy37.py — S37 Horizontal Support/Resistance Pivot Bounce, RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด: หา pivot high/low (fractal — แท่งกลางสูง/ต่ำสุดเทียบ N แท่งซ้าย-ขวา) ย้อนหลัง
MAX_LEVEL_AGE_BARS แท่ง เพื่อสร้างเป็นแนวรับ/แนวต้านแนวนอน เมื่อราคาแท่งล่าสุดแตะเข้าใกล้ระดับ
(ภายใน TOUCH_ATR_MULT x ATR) แล้วปิดถอยกลับออกจากระดับ (rejection wick) >= REJECT_ATR_MULT x ATR
เข้าตามทิศ bounce ยืนยันด้วย htf_trend (M15/EMA50) — เป็น pullback-to-level continuation entry
ไม่ใช่ reversal เดา top/bottom ของช่วงเทรนด์
"""

S37_DEFAULTS = {
    "ENTRY_TF": "M5",
    "PIVOT_WING": 3,              # จำนวนแท่งซ้าย-ขวาที่ต้องสูง/ต่ำกว่าเพื่อนับเป็น pivot (fractal)
    "MAX_LEVEL_AGE_BARS": 120,     # ใช้ pivot ที่เกิดภายใน N แท่งล่าสุดเท่านั้น
    "TOUCH_ATR_MULT": 0.3,        # ราคาต้องแตะใกล้ระดับภายใน mult x ATR ถึงนับว่า "แตะ"
    "REJECT_ATR_MULT": 0.25,      # ต้องปิดถอยห่างจากระดับ >= mult x ATR (ยืนยัน rejection)
    "SL_ATR_MULT": 1.0,
    "TP_RR": 1.0,
    "MAX_RISK_ATR_MULT": 4.0,
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
    return S37_DEFAULTS[key]


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


def _find_pivot_levels(closed_rates, cfg):
    """
    หา fractal pivot high/low ย้อนหลัง MAX_LEVEL_AGE_BARS แท่ง — pivot high ที่ index i ต้องมี
    high[i] > high ของ wing แท่งซ้าย-ขวาทั้งหมด, pivot low กลับกัน
    คืน (res_levels: list[float], sup_levels: list[float])
    """
    wing = int(_cfg(cfg, "PIVOT_WING"))
    max_age = int(_cfg(cfg, "MAX_LEVEL_AGE_BARS"))
    n = len(closed_rates)
    start = max(wing, n - max_age)
    res_levels, sup_levels = [], []
    for i in range(start, n - wing):
        h = float(closed_rates[i]["high"]); l = float(closed_rates[i]["low"])
        is_res = all(h > float(closed_rates[i - k]["high"]) and h > float(closed_rates[i + k]["high"])
                     for k in range(1, wing + 1))
        is_sup = all(l < float(closed_rates[i - k]["low"]) and l < float(closed_rates[i + k]["low"])
                     for k in range(1, wing + 1))
        if is_res:
            res_levels.append(h)
        if is_sup:
            sup_levels.append(l)
    return res_levels, sup_levels


def detect_s37(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    wing = int(_cfg(cfg, "PIVOT_WING"))
    need = int(_cfg(cfg, "MAX_LEVEL_AGE_BARS")) + wing * 2 + 20
    if rates is None or len(rates) < min(need, 60):
        return {"signal": "WAIT", "reason": f"S37: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S37: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S37: ATR ไม่ได้"}

    # pivot ต้องยืนยันด้วยแท่งหลัง wing แท่ง — ตัดท้าย wing แท่งสุดท้ายออกตอนหา level
    pivot_rates = closed[:-wing] if wing > 0 else closed
    res_levels, sup_levels = _find_pivot_levels(pivot_rates, cfg)

    cur = closed[-1]
    cc = float(cur["close"]); ch = float(cur["high"]); cl = float(cur["low"])
    touch_buf = atr * float(_cfg(cfg, "TOUCH_ATR_MULT"))
    reject_buf = atr * float(_cfg(cfg, "REJECT_ATR_MULT"))

    direction = None
    level_hit = None
    # แตะแนวรับ (low เข้าใกล้ level ภายใน touch_buf) แล้วปิดถอยขึ้นเหนือ level >= reject_buf -> BUY
    for lvl in sup_levels:
        if cl <= lvl + touch_buf and cc >= lvl + reject_buf and cc > cl:
            direction = "BUY"; level_hit = lvl
            break
    if direction is None:
        for lvl in res_levels:
            if ch >= lvl - touch_buf and cc <= lvl - reject_buf and cc < ch:
                direction = "SELL"; level_hit = lvl
                break
    if direction is None:
        return {"signal": "WAIT", "reason": "S37: ไม่มี rejection ที่ระดับ S/R"}

    entry = round(cc, 2)
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    if direction == "BUY":
        sl = round(min(level_hit, cl) - sl_buf, 2)
    else:
        sl = round(max(level_hit, ch) + sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S37: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S37: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S37: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S37: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S37: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S37: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 37 SR_bounce+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"S/R bounce level={level_hit:.2f}\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_37(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s37(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
