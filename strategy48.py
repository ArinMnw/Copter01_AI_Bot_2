"""
strategy48.py — S48 MACD crossover entry, RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด: MACD = EMA(FAST) - EMA(SLOW), signal line = EMA(SIGNAL) ของ MACD เข้า BUY ตอน MACD ตัดขึ้น
เหนือ signal line (bullish crossover), SELL ตอนตัดลงต่ำกว่า (bearish crossover) — momentum entry
ล้วน ยืนยันด้วย htf_trend (M15/EMA50) ทางเลือก
"""

S48_DEFAULTS = {
    "ENTRY_TF": "M5",
    "MACD_FAST": 12,
    "MACD_SLOW": 26,
    "MACD_SIGNAL": 9,
    "MIN_HIST_ATR": 0.0,           # histogram ขนาดต่ำสุด (x ATR) ตอน crossover กันสัญญาณอ่อน
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
    return S48_DEFAULTS[key]


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


def _ema_series(values, period):
    n = len(values)
    out = [None] * n
    if n < period:
        return out
    k = 2.0 / (period + 1)
    sma = sum(values[:period]) / period
    out[period - 1] = sma
    prev = sma
    for i in range(period, n):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def _macd_series(closes, fast, slow, signal):
    ema_fast = _ema_series(closes, fast)
    ema_slow = _ema_series(closes, slow)
    n = len(closes)
    macd = [None] * n
    for i in range(n):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd[i] = ema_fast[i] - ema_slow[i]
    valid = [v for v in macd if v is not None]
    if len(valid) < signal:
        return macd, [None] * n
    sig_line = [None] * n
    start = next(i for i, v in enumerate(macd) if v is not None)
    macd_valid_vals = macd[start:]
    sig_valid = _ema_series(macd_valid_vals, signal)
    for j, v in enumerate(sig_valid):
        sig_line[start + j] = v
    return macd, sig_line


def detect_s48(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    slow = int(_cfg(cfg, "MACD_SLOW"))
    signal = int(_cfg(cfg, "MACD_SIGNAL"))
    need = slow + signal + 20
    if rates is None or len(rates) < min(need, 80):
        return {"signal": "WAIT", "reason": "S48: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S48: นอก session"}

    closed = rates[:-1]
    if len(closed) < need:
        return {"signal": "WAIT", "reason": "S48: ข้อมูลไม่พอ"}

    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S48: ATR ไม่ได้"}

    closes = [float(r["close"]) for r in closed]
    fast = int(_cfg(cfg, "MACD_FAST"))
    macd, sig_line = _macd_series(closes, fast, slow, signal)

    if macd[-1] is None or macd[-2] is None or sig_line[-1] is None or sig_line[-2] is None:
        return {"signal": "WAIT", "reason": "S48: MACD ไม่พอ"}

    prev_diff = macd[-2] - sig_line[-2]
    cur_diff = macd[-1] - sig_line[-1]

    direction = None
    if prev_diff <= 0 and cur_diff > 0:
        direction = "BUY"
    elif prev_diff >= 0 and cur_diff < 0:
        direction = "SELL"
    if direction is None:
        return {"signal": "WAIT", "reason": "S48: ไม่มี MACD crossover"}

    min_hist = float(_cfg(cfg, "MIN_HIST_ATR")) * atr
    if abs(cur_diff) < min_hist:
        return {"signal": "WAIT", "reason": "S48: histogram เล็กเกินไป"}

    cur = closed[-1]
    entry = round(float(cur["close"]), 2)
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    if direction == "BUY":
        sl = round(entry - sl_buf, 2)
    else:
        sl = round(entry + sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S48: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S48: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S48: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S48: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S48: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S48: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 48 MACD_cross+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"MACD crossover diff={cur_diff:.4f}\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_48(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s48(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
