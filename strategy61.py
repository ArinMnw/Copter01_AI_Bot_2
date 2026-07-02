"""
strategy61.py — S61 CYQONX Three-Line Mean Reversion, RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

ถอดจาก CYQONX Three-Line ให้เป็นกฎที่ backtest ได้:
- mean line = EMA/SMA equilibrium
- upper/lower = mean ± k * deviation (ATR หรือ rolling std)
- position = (close - mean) / deviation
- phase turn = oscillator เริ่มกลับทิศเข้าหา mean
"""

S61_DEFAULTS = {
    "ENTRY_TF": "M5",
    "MEAN_TYPE": "ema",            # ema | sma
    "MEAN_PERIOD": 48,
    "DEV_TYPE": "atr",             # atr | std
    "DEV_PERIOD": 48,
    "BAND_MULT": 1.5,
    "ENTRY_Z": 1.0,
    "PHASE_LOOKBACK": 3,
    "SLOPE_FILTER": "none",        # none | mean_flat | counter_slope
    "MAX_MEAN_SLOPE_ATR": 0.25,
    "SL_ATR_MULT": 1.0,
    "TP_MODE": "mean",             # mean | rr
    "TP_RR": 1.0,
    "MAX_RISK_ATR_MULT": 5.0,
    "MIN_GAP_BARS": 1,
    "SESSION_FILTER": True,
    "SESSIONS": [("08:00", "23:00")],

    "RISK_PCT": 0.5,
    "DD_CONTROL": "circuit_breaker",
    "CONSEC_LOSS_TRIGGER": 3,
    "REDUCED_RISK_PCT": 0.4,
    "COOLDOWN_TRADES": 10,

    "CONFIRMATION_TYPE": "none",
    "HTF_TF": "M15",
    "HTF_EMA_PERIOD": 50,
    "HTF_SLOPE_BARS": 5,
    "ADX_PERIOD": 14,
    "ADX_MIN_THRESHOLD": 0.0,
}


def _cfg(cfg, key):
    if cfg and key in cfg:
        return cfg[key]
    return S61_DEFAULTS[key]


def _parse_time(s):
    from datetime import time
    h, m = map(int, s.split(":"))
    return time(h, m)


def _in_session(dt_bkk, cfg):
    if not _cfg(cfg, "SESSION_FILTER") or dt_bkk is None:
        return True
    cur = dt_bkk.time()
    for start_str, end_str in _cfg(cfg, "SESSIONS"):
        if _parse_time(start_str) <= cur < _parse_time(end_str):
            return True
    return False


def _atr(rates, period=14):
    trs = []
    for i, b in enumerate(rates):
        h = float(b["high"]); l = float(b["low"])
        if i == 0:
            trs.append(h - l)
        else:
            pc = float(rates[i - 1]["close"])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not trs:
        return 0.0
    if len(trs) <= period:
        return sum(trs) / len(trs)
    val = sum(trs[:period]) / period
    for tr in trs[period:]:
        val = (val * (period - 1) + tr) / period
    return val


def _ema(values, period):
    if not values:
        return 0.0
    k = 2.0 / (period + 1.0)
    val = values[0]
    for x in values[1:]:
        val = val + k * (x - val)
    return val


def _std(values):
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((x - mean) ** 2 for x in values) / len(values)) ** 0.5


def _mean(values, cfg):
    period = int(_cfg(cfg, "MEAN_PERIOD"))
    src = values[-period:]
    if _cfg(cfg, "MEAN_TYPE") == "sma":
        return sum(src) / len(src)
    return _ema(src, period)


def _state(closed, cfg):
    mean_period = int(_cfg(cfg, "MEAN_PERIOD"))
    dev_period = int(_cfg(cfg, "DEV_PERIOD"))
    need = max(mean_period, dev_period) + 5
    if len(closed) < need:
        return None
    closes = [float(b["close"]) for b in closed]
    mean_now = _mean(closes, cfg)
    mean_prev = _mean(closes[:-int(_cfg(cfg, "PHASE_LOOKBACK"))], cfg)
    if _cfg(cfg, "DEV_TYPE") == "std":
        dev = _std(closes[-dev_period:])
    else:
        dev = _atr(closed[-(dev_period + 20):], dev_period)
    atr14 = _atr(closed[-40:], 14)
    if dev <= 0 or atr14 <= 0:
        return None
    close_now = closes[-1]
    osc = [c - mean_now for c in closes[-6:]]
    z = (close_now - mean_now) / dev
    slope_atr = (mean_now - mean_prev) / atr14 if atr14 > 0 else 0.0
    return mean_now, dev, atr14, z, osc, slope_atr


def detect_s61(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    if rates is None or len(rates) < 80:
        return {"signal": "WAIT", "reason": "S61: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S61: นอก session"}
    closed = rates[:-1]
    st = _state(closed, cfg)
    if st is None:
        return {"signal": "WAIT", "reason": "S61: state ไม่พร้อม"}
    mean_now, dev, atr14, z, osc, slope_atr = st
    phase_lb = int(_cfg(cfg, "PHASE_LOOKBACK"))
    entry_z = float(_cfg(cfg, "ENTRY_Z"))

    recent = osc[-phase_lb:]
    direction = None
    if z <= -entry_z and recent[-1] > recent[-2] and min(recent) == recent[-2]:
        direction = "BUY"
    elif z >= entry_z and recent[-1] < recent[-2] and max(recent) == recent[-2]:
        direction = "SELL"
    if direction is None:
        return {"signal": "WAIT", "reason": "S61: ยังไม่มี phase turn ที่ปลาย band"}

    slope_filter = _cfg(cfg, "SLOPE_FILTER")
    max_slope = float(_cfg(cfg, "MAX_MEAN_SLOPE_ATR"))
    if slope_filter == "mean_flat" and abs(slope_atr) > max_slope:
        return {"signal": "WAIT", "reason": "S61: mean slope แรงเกิน"}
    if slope_filter == "counter_slope":
        if direction == "BUY" and slope_atr < -max_slope:
            return {"signal": "WAIT", "reason": "S61: mean slope ลงแรง"}
        if direction == "SELL" and slope_atr > max_slope:
            return {"signal": "WAIT", "reason": "S61: mean slope ขึ้นแรง"}

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type == "htf_trend":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S61: ไม่มี HTF context"}
        # mean reversion: trade back against stretched HTF extension only when HTF has started opposing it.
        if direction == "BUY" and not htf_ctx.get("trend_down", False):
            return {"signal": "WAIT", "reason": "S61: HTF ไม่ลงสำหรับ BUY reversion"}
        if direction == "SELL" and not htf_ctx.get("trend_up", False):
            return {"signal": "WAIT", "reason": "S61: HTF ไม่ขึ้นสำหรับ SELL reversion"}

    cur = closed[-1]
    entry = round(float(cur["close"]), 2)
    sl_buf = float(_cfg(cfg, "SL_ATR_MULT")) * atr14
    if direction == "BUY":
        sl = round(min(float(cur["low"]), entry) - sl_buf, 2)
        tp = round(mean_now, 2) if _cfg(cfg, "TP_MODE") == "mean" else round(entry + float(_cfg(cfg, "TP_RR")) * (entry - sl), 2)
        risk = entry - sl
        if not (0 < risk <= float(_cfg(cfg, "MAX_RISK_ATR_MULT")) * atr14 and tp > entry):
            return {"signal": "WAIT", "reason": "S61: risk/tp ผิดปกติ"}
    else:
        sl = round(max(float(cur["high"]), entry) + sl_buf, 2)
        tp = round(mean_now, 2) if _cfg(cfg, "TP_MODE") == "mean" else round(entry - float(_cfg(cfg, "TP_RR")) * (sl - entry), 2)
        risk = sl - entry
        if not (0 < risk <= float(_cfg(cfg, "MAX_RISK_ATR_MULT")) * atr14 and tp < entry):
            return {"signal": "WAIT", "reason": "S61: risk/tp ผิดปกติ"}

    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 61 CYQONX_ThreeLine {'BUY' if direction == 'BUY' else 'SELL'}",
        "reason": f"CYQONX z={z:.2f} mean={mean_now:.2f} dev={dev:.2f} slopeATR={slope_atr:.2f}",
        "order_mode": "market", "signal_bar_time": int(cur["time"]), "atr_at_signal": atr14,
        "confirmation_type": conf_type,
    }


def strategy_61(rates, tf: str = "", cfg: dict | None = None):
    return detect_s61(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
