"""
strategy47.py — S47 SuperTrend flip entry, RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด: SuperTrend indicator (ATR-band trailing line) — แต่ละแท่งคำนวณ basic upper/lower band
จาก (high+low)/2 ± mult*ATR แล้ว trail แบบ ratchet (final band ขยับเข้าหาราคาเท่านั้น ไม่ขยับออก)
trend พลิกขึ้น (downtrend->uptrend) เมื่อ close ทะลุ final upperband ขึ้นไป, พลิกลงเมื่อ close
ทะลุ final lowerband ลงมา — เข้า BUY/SELL ที่แท่งที่ trend พลิกครั้งแรก (flip bar) ยืนยันด้วย
htf_trend (M15/EMA50) ทางเลือก
"""

S47_DEFAULTS = {
    "ENTRY_TF": "M5",
    "ST_ATR_PERIOD": 10,
    "ST_ATR_MULT": 3.0,
    "SL_ATR_MULT": 1.0,
    "TP_RR": 1.5,
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
    return S47_DEFAULTS[key]


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


def _supertrend_series(closed_rates, period, mult):
    """
    คำนวณ SuperTrend ratchet trailing band ทั้งซีรีส์ — คืน list ของ (final_upper, final_lower,
    trend) ต่อแท่ง โดย trend=1 (up) / -1 (down) — index ตรงกับ closed_rates
    """
    n = len(closed_rates)
    if n < period + 2:
        return None

    atr_vals = []
    trs = []
    for i in range(n):
        h = float(closed_rates[i]["high"]); l = float(closed_rates[i]["low"])
        if i == 0:
            trs.append(h - l)
        else:
            pc = float(closed_rates[i - 1]["close"])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        if i < period - 1:
            atr_vals.append(None)
        elif i == period - 1:
            atr_vals.append(sum(trs[:period]) / period)
        else:
            atr_vals.append((atr_vals[-1] * (period - 1) + trs[i]) / period)

    final_upper = [None] * n
    final_lower = [None] * n
    trend = [None] * n

    for i in range(n):
        if atr_vals[i] is None:
            continue
        h = float(closed_rates[i]["high"]); l = float(closed_rates[i]["low"])
        c = float(closed_rates[i]["close"])
        basic_upper = (h + l) / 2.0 + mult * atr_vals[i]
        basic_lower = (h + l) / 2.0 - mult * atr_vals[i]

        prev_idx = i - 1
        if prev_idx >= 0 and final_upper[prev_idx] is not None:
            pc = float(closed_rates[prev_idx]["close"])
            fu = basic_upper if (basic_upper < final_upper[prev_idx] or pc > final_upper[prev_idx]) else final_upper[prev_idx]
            fl = basic_lower if (basic_lower > final_lower[prev_idx] or pc < final_lower[prev_idx]) else final_lower[prev_idx]
        else:
            fu, fl = basic_upper, basic_lower
        final_upper[i] = fu
        final_lower[i] = fl

        if prev_idx >= 0 and trend[prev_idx] is not None:
            prev_trend = trend[prev_idx]
            if prev_trend == 1:
                trend[i] = -1 if c < fl else 1
            else:
                trend[i] = 1 if c > fu else -1
        else:
            trend[i] = 1 if c > fu else -1

    return final_upper, final_lower, trend


def detect_s47(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    period = int(_cfg(cfg, "ST_ATR_PERIOD"))
    mult = float(_cfg(cfg, "ST_ATR_MULT"))
    need = period + 30
    if rates is None or len(rates) < min(need, 60):
        return {"signal": "WAIT", "reason": "S47: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S47: นอก session"}

    closed = rates[:-1]
    if len(closed) < period + 2:
        return {"signal": "WAIT", "reason": "S47: ข้อมูลไม่พอ"}

    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S47: ATR ไม่ได้"}

    res = _supertrend_series(closed, period, mult)
    if res is None:
        return {"signal": "WAIT", "reason": "S47: คำนวณ SuperTrend ไม่ได้"}
    final_upper, final_lower, trend = res

    if trend[-1] is None or trend[-2] is None:
        return {"signal": "WAIT", "reason": "S47: trend ไม่พอ"}

    direction = None
    if trend[-2] == -1 and trend[-1] == 1:
        direction = "BUY"
    elif trend[-2] == 1 and trend[-1] == -1:
        direction = "SELL"
    if direction is None:
        return {"signal": "WAIT", "reason": "S47: ไม่มี trend flip"}

    cur = closed[-1]
    entry = round(float(cur["close"]), 2)
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    st_line = final_lower[-1] if direction == "BUY" else final_upper[-1]

    if direction == "BUY":
        sl = round(min(st_line, entry) - sl_buf, 2)
    else:
        sl = round(max(st_line, entry) + sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S47: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S47: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S47: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S47: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S47: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S47: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 47 SuperTrend_flip+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"SuperTrend flip period={period} mult={mult}\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_47(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s47(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
