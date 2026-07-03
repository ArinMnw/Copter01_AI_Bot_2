"""
strategy67.py - S67 All-in-4S Clear Candle Reversal, RESEARCH/BACKTEST-ONLY

Standalone only: not imported by scanner.py/trailing.py/main.py.

Computable idea from All-in-4S clear-candle notes:
- price is pushed hard one way, then pulled back to close the opposite color
- the rejection wick should be obvious
- the close should cover the prior candle context, not only change candle color
"""

S67_DEFAULTS = {
    "ENTRY_TF": "M5",
    "MIN_BODY_ATR": 0.12,
    "MIN_RANGE_ATR": 0.80,
    "WICK_BODY_MULT": 1.20,
    "WICK_RANGE_MIN": 0.35,
    "CLOSE_COVER": "body",          # body | wick
    "TREND_LOOKBACK": 20,
    "TREND_MIN_ATR": 1.5,
    "MODE": "reversal",             # reversal | continuation
    "SL_ATR_MULT": 0.25,
    "TP_RR": 1.15,
    "MAX_RISK_ATR_MULT": 4.0,
    "MIN_GAP_BARS": 4,
    "SESSION_FILTER": True,
    "SESSIONS": [("08:00", "23:00")],
    "RISK_PCT": 0.5,
    "DD_CONTROL": "circuit_breaker",
    "CONSEC_LOSS_TRIGGER": 3,
    "REDUCED_RISK_PCT": 0.35,
    "COOLDOWN_TRADES": 10,
}


def _cfg(cfg, key):
    if cfg and key in cfg:
        return cfg[key]
    return S67_DEFAULTS[key]


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
        h = float(b["high"])
        l = float(b["low"])
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


def _body(b):
    return abs(float(b["close"]) - float(b["open"]))


def _range(b):
    return max(0.0001, float(b["high"]) - float(b["low"]))


def _bull(b):
    return float(b["close"]) > float(b["open"])


def _bear(b):
    return float(b["close"]) < float(b["open"])


def _upper_wick(b):
    return float(b["high"]) - max(float(b["open"]), float(b["close"]))


def _lower_wick(b):
    return min(float(b["open"]), float(b["close"])) - float(b["low"])


def _trend_bias(closed, j, atr, cfg):
    lb = int(_cfg(cfg, "TREND_LOOKBACK"))
    if j < lb:
        return None
    start = closed[j - lb]
    cur = closed[j]
    move = float(cur["close"]) - float(start["close"])
    if abs(move) < float(_cfg(cfg, "TREND_MIN_ATR")) * atr:
        return None
    return "UP" if move > 0 else "DOWN"


def _detect_closed(closed, j, cfg, atr_value=None):
    if j < int(_cfg(cfg, "TREND_LOOKBACK")) + 5:
        return None
    atr = atr_value if atr_value is not None else _atr(closed[max(0, j - 70):j + 1], 14)
    if atr <= 0:
        return None
    prev = closed[j - 1]
    cur = closed[j]
    body = _body(cur)
    rng = _range(cur)
    if body < float(_cfg(cfg, "MIN_BODY_ATR")) * atr:
        return None
    if rng < float(_cfg(cfg, "MIN_RANGE_ATR")) * atr:
        return None

    trend = _trend_bias(closed, j - 1, atr, cfg)
    cover_mode = _cfg(cfg, "CLOSE_COVER")
    lower = _lower_wick(cur)
    upper = _upper_wick(cur)
    wick_body_mult = float(_cfg(cfg, "WICK_BODY_MULT"))
    wick_range_min = float(_cfg(cfg, "WICK_RANGE_MIN"))

    bull_clear = (
        _bull(cur)
        and lower >= wick_body_mult * body
        and lower / rng >= wick_range_min
        and float(cur["low"]) < float(prev["low"])
    )
    bear_clear = (
        _bear(cur)
        and upper >= wick_body_mult * body
        and upper / rng >= wick_range_min
        and float(cur["high"]) > float(prev["high"])
    )
    if cover_mode == "wick":
        bull_clear = bull_clear and float(cur["close"]) > float(prev["high"])
        bear_clear = bear_clear and float(cur["close"]) < float(prev["low"])
    else:
        bull_clear = bull_clear and float(cur["close"]) > max(float(prev["open"]), float(prev["close"]))
        bear_clear = bear_clear and float(cur["close"]) < min(float(prev["open"]), float(prev["close"]))

    sig = None
    if _cfg(cfg, "MODE") == "reversal":
        if bull_clear and trend == "DOWN":
            sig = "BUY"
        elif bear_clear and trend == "UP":
            sig = "SELL"
    else:
        if bull_clear and trend == "UP":
            sig = "BUY"
        elif bear_clear and trend == "DOWN":
            sig = "SELL"
    if sig is None:
        return None

    entry = round(float(cur["close"]), 2)
    sl_buf = float(_cfg(cfg, "SL_ATR_MULT")) * atr
    if sig == "BUY":
        sl = round(float(cur["low"]) - sl_buf, 2)
        risk = entry - sl
        tp = round(entry + float(_cfg(cfg, "TP_RR")) * risk, 2)
    else:
        sl = round(float(cur["high"]) + sl_buf, 2)
        risk = sl - entry
        tp = round(entry - float(_cfg(cfg, "TP_RR")) * risk, 2)
    if not (0 < risk <= float(_cfg(cfg, "MAX_RISK_ATR_MULT")) * atr):
        return None

    return {
        "signal": sig,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "pattern": f"ท่าที่ 67 AllIn4S_Clear_Candle_{sig}",
        "reason": (
            f"clear candle mode={_cfg(cfg, 'MODE')} cover={cover_mode} "
            f"trend={trend} wick/body={(lower if sig == 'BUY' else upper)/max(body, 0.0001):.2f} "
            f"riskATR={risk/atr:.2f}"
        ),
        "order_mode": "market",
        "signal_bar_time": int(cur["time"]),
        "atr_at_signal": atr,
    }


def detect_s67(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    if rates is None or len(rates) < 80:
        return {"signal": "WAIT", "reason": "S67: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S67: นอก session"}
    closed = rates[:-1]
    found = _detect_closed(closed, len(closed) - 1, cfg or S67_DEFAULTS)
    if found is None:
        return {"signal": "WAIT", "reason": "S67: ยังไม่ครบ clear candle"}
    return found


def strategy_67(rates, tf: str = "", cfg: dict | None = None):
    return detect_s67(rates, tf=tf, dt_bkk=None, cfg=cfg)
