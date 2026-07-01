"""
strategy39.py — S39 Demand/Supply Zone (base-and-breakout, SMC), RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด SMC: **Demand/Supply zone** เกิดจาก "base" (กลุ่มแท่งตัวเล็ก consolidate, range <=
BASE_ATR_MULT x ATR) ตามด้วย "impulse" (แท่งใหญ่ทะลุออกจาก base, range >= IMPULSE_ATR_MULT x ATR)
— โซน base ที่ราคาวิ่งออกไปกลายเป็น demand zone (ถ้า impulse ขึ้น) หรือ supply zone (ถ้า impulse
ลง) เมื่อราคาย้อนกลับมาที่โซนนี้ (โดยยังไม่ถูกฝ่าทะลุ) เข้าต่อทิศ impulse เดิม (continuation)
ยืนยันด้วย htf_trend (M15/EMA50) เหมือน A-E — ต่างจาก S37(fractal pivot) และ S38(fib swing) ที่ใช้
"โซน consolidation ก่อนทะลุ" แทนจุดเดียว
"""

S39_DEFAULTS = {
    "ENTRY_TF": "M5",
    "BASE_BARS": 3,                # จำนวนแท่ง consolidation ขั้นต่ำก่อน impulse
    "BASE_ATR_MULT": 0.5,          # แท่ง base ต้องมี range <= mult x ATR (ตัวเล็ก)
    "IMPULSE_ATR_MULT": 1.2,       # แท่ง impulse ต้องมี range >= mult x ATR (ตัวใหญ่ทะลุ)
    "MAX_ZONE_AGE_BARS": 40,       # โซนต้องเกิดภายใน N แท่งล่าสุด
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
    return S39_DEFAULTS[key]


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


def _find_active_zone(closed_rates, atr, cfg):
    """
    หา base+impulse ล่าสุดที่ยังไม่ถูกฝ่าทะลุ (จากท้ายสุดถอยหลัง) — impulse แท่งที่ i ใหญ่พอ,
    base = BASE_BARS แท่งก่อนหน้า i ที่ตัวเล็กพอ, zone = [min(low ของ base), max(high ของ base)]
    คืน (direction, zone_top, zone_bottom, age) หรือ None
    """
    base_n = int(_cfg(cfg, "BASE_BARS"))
    base_mult = float(_cfg(cfg, "BASE_ATR_MULT"))
    impulse_mult = float(_cfg(cfg, "IMPULSE_ATR_MULT"))
    max_age = int(_cfg(cfg, "MAX_ZONE_AGE_BARS"))
    n = len(closed_rates)
    lookback_start = max(base_n, n - max_age - 1)

    for i in range(n - 1, lookback_start, -1):
        if i - base_n < 0:
            break
        imp = closed_rates[i]
        imp_range = float(imp["high"]) - float(imp["low"])
        if imp_range < impulse_mult * atr:
            continue
        base_rates = closed_rates[i - base_n:i]
        if len(base_rates) == 0:
            continue
        if any((float(b["high"]) - float(b["low"])) > base_mult * atr for b in base_rates):
            continue
        zone_top = max(float(b["high"]) for b in base_rates)
        zone_bottom = min(float(b["low"]) for b in base_rates)

        is_bull = float(imp["close"]) > float(imp["open"]) and float(imp["close"]) > zone_top
        is_bear = float(imp["close"]) < float(imp["open"]) and float(imp["close"]) < zone_bottom
        if not (is_bull or is_bear):
            continue

        direction = "BUY" if is_bull else "SELL"
        # เช็คว่าโซนยังไม่ถูกฝ่าทะลุ (close ฝั่งตรงข้ามผ่านโซนไปแล้ว) นับจากหลัง impulse
        violated = False
        for k in range(i + 1, n):
            c = float(closed_rates[k]["close"])
            if direction == "BUY" and c < zone_bottom:
                violated = True; break
            if direction == "SELL" and c > zone_top:
                violated = True; break
        if violated:
            continue
        age = n - 1 - i
        return (direction, zone_top, zone_bottom, age)
    return None


def detect_s39(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    base_n = int(_cfg(cfg, "BASE_BARS"))
    max_age = int(_cfg(cfg, "MAX_ZONE_AGE_BARS"))
    need = base_n + max_age + 20
    if rates is None or len(rates) < min(need, 60):
        return {"signal": "WAIT", "reason": "S39: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S39: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S39: ATR ไม่ได้"}

    zone = _find_active_zone(closed, atr, cfg)
    if zone is None:
        return {"signal": "WAIT", "reason": "S39: ไม่พบ demand/supply zone ที่ยังไม่ถูกฝ่าทะลุ"}
    direction, zone_top, zone_bottom, _ = zone

    cur = closed[-1]
    cc = float(cur["close"])

    if direction == "BUY":
        if not (zone_bottom <= cc <= zone_top):
            return {"signal": "WAIT", "reason": "S39: ราคายังไม่ย้อนกลับเข้า demand zone"}
        entry = round(cc, 2)
        sl = round(zone_bottom - float(_cfg(cfg, "SL_ATR_MULT")) * atr, 2)
    else:
        if not (zone_bottom <= cc <= zone_top):
            return {"signal": "WAIT", "reason": "S39: ราคายังไม่ย้อนกลับเข้า supply zone"}
        entry = round(cc, 2)
        sl = round(zone_top + float(_cfg(cfg, "SL_ATR_MULT")) * atr, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S39: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S39: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S39: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S39: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S39: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S39: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 39 DemandSupply+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"zone=[{zone_bottom:.2f},{zone_top:.2f}]\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_39(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s39(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
