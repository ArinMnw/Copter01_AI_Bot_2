"""
strategy62.py - S62 All-in-4S First-Wave Close-Cover Reversal, RESEARCH/BACKTEST-ONLY

Standalone only: not imported by scanner.py/trailing.py/main.py.

Research source: local All-in-4S PDF notes. The computable version keeps the
parts that appear repeatedly in the material:
- reversal at a meaningful H/L or swept liquidity area
- first reversal wave, not the later repeated wave
- candle closes covering the prior candle body or full wick
- signal candle body must be meaningful but not oversized
"""

S62_DEFAULTS = {
    "ENTRY_TF": "M5",
    "TREND_LOOKBACK": 10,
    "PIVOT_LOOKBACK": 8,
    "LEVEL_LOOKBACK": 48,
    "LEVEL_TOL_ATR": 0.35,
    "ROUND_STEP": 5.0,
    "ROUND_TOL_ATR": 0.25,
    "LEVEL_MODE": "sweep_or_round",      # sweep | near | round | sweep_or_round | any
    "COVER_MODE": "wick",                # body | wick
    "MIN_BODY_ATR": 0.12,
    "MAX_BODY_ATR": 1.80,
    "MIN_BODY_RATIO": 0.35,
    "MAX_WICK_RATIO": 0.75,
    "FIRST_WAVE_BARS": 12,
    "SL_ATR_MULT": 0.45,
    "TP_RR": 1.20,
    "MAX_RISK_ATR_MULT": 4.0,
    "MIN_GAP_BARS": 3,
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
    return S62_DEFAULTS[key]


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


def _is_bull(b):
    return float(b["close"]) > float(b["open"])


def _is_bear(b):
    return float(b["close"]) < float(b["open"])


def _round_hit(price, atr, cfg):
    step = float(_cfg(cfg, "ROUND_STEP"))
    if step <= 0 or atr <= 0:
        return False
    nearest = round(price / step) * step
    return abs(price - nearest) <= float(_cfg(cfg, "ROUND_TOL_ATR")) * atr


def _level_context(closed, j, sig, atr, cfg):
    pivot_lb = int(_cfg(cfg, "PIVOT_LOOKBACK"))
    level_lb = int(_cfg(cfg, "LEVEL_LOOKBACK"))
    tol = float(_cfg(cfg, "LEVEL_TOL_ATR")) * atr
    cur = closed[j]
    prior_start = max(0, j - level_lb)
    pivot_start = max(0, j - pivot_lb)
    if j <= prior_start + 2 or atr <= 0:
        return False, "no_level_data"

    prior = closed[prior_start:j]
    recent = closed[pivot_start:j]
    if sig == "BUY":
        prior_low = min(float(b["low"]) for b in prior)
        recent_low = min(float(b["low"]) for b in recent)
        extreme = float(cur["low"])
        swept = extreme <= recent_low
        near = abs(extreme - prior_low) <= tol
        round_ok = _round_hit(extreme, atr, cfg)
    else:
        prior_high = max(float(b["high"]) for b in prior)
        recent_high = max(float(b["high"]) for b in recent)
        extreme = float(cur["high"])
        swept = extreme >= recent_high
        near = abs(extreme - prior_high) <= tol
        round_ok = _round_hit(extreme, atr, cfg)

    mode = _cfg(cfg, "LEVEL_MODE")
    if mode == "any":
        ok = True
    elif mode == "sweep":
        ok = swept
    elif mode == "near":
        ok = near
    elif mode == "round":
        ok = round_ok
    else:
        ok = swept or round_ok
    return ok, f"swept={int(swept)} near={int(near)} round={int(round_ok)}"


def _recent_same_signal(closed, j, sig, cfg):
    look = int(_cfg(cfg, "FIRST_WAVE_BARS"))
    start = max(2, j - look)
    for k in range(start, j):
        prev = closed[k - 1]
        cur = closed[k]
        if sig == "BUY":
            if _is_bull(cur) and float(cur["close"]) > float(prev["high"]):
                return True
        else:
            if _is_bear(cur) and float(cur["close"]) < float(prev["low"]):
                return True
    return False


def _detect_closed(closed, j, cfg, closes=None, atr_value=None):
    if j < max(int(_cfg(cfg, "TREND_LOOKBACK")), int(_cfg(cfg, "LEVEL_LOOKBACK"))) + 3:
        return None
    cur = closed[j]
    prev = closed[j - 1]
    atr = atr_value if atr_value is not None else _atr(closed[max(0, j - 60):j + 1], 14)
    if atr <= 0:
        return None

    body = _body(cur)
    rng = _range(cur)
    if body < float(_cfg(cfg, "MIN_BODY_ATR")) * atr:
        return None
    if body > float(_cfg(cfg, "MAX_BODY_ATR")) * atr:
        return None
    if body / rng < float(_cfg(cfg, "MIN_BODY_RATIO")):
        return None

    trend_lb = int(_cfg(cfg, "TREND_LOOKBACK"))
    if closes is None:
        closes = [float(b["close"]) for b in closed]
    down_context = closes[j - 1] < closes[j - trend_lb]
    up_context = closes[j - 1] > closes[j - trend_lb]

    sig = None
    cover_mode = _cfg(cfg, "COVER_MODE")
    if _is_bull(cur) and down_context:
        body_cover = float(cur["close"]) > max(float(prev["open"]), float(prev["close"]))
        wick_cover = float(cur["close"]) > float(prev["high"])
        if (cover_mode == "wick" and wick_cover) or (cover_mode == "body" and body_cover):
            sig = "BUY"
    elif _is_bear(cur) and up_context:
        body_cover = float(cur["close"]) < min(float(prev["open"]), float(prev["close"]))
        wick_cover = float(cur["close"]) < float(prev["low"])
        if (cover_mode == "wick" and wick_cover) or (cover_mode == "body" and body_cover):
            sig = "SELL"
    if sig is None:
        return None

    if _recent_same_signal(closed, j, sig, cfg):
        return None
    level_ok, level_reason = _level_context(closed, j, sig, atr, cfg)
    if not level_ok:
        return None

    entry = round(float(cur["close"]), 2)
    sl_buf = float(_cfg(cfg, "SL_ATR_MULT")) * atr
    if sig == "BUY":
        sl = round(min(float(cur["low"]), float(prev["low"])) - sl_buf, 2)
        risk = entry - sl
        tp = round(entry + float(_cfg(cfg, "TP_RR")) * risk, 2)
    else:
        sl = round(max(float(cur["high"]), float(prev["high"])) + sl_buf, 2)
        risk = sl - entry
        tp = round(entry - float(_cfg(cfg, "TP_RR")) * risk, 2)
    if not (0 < risk <= float(_cfg(cfg, "MAX_RISK_ATR_MULT")) * atr):
        return None
    if sig == "BUY" and tp <= entry:
        return None
    if sig == "SELL" and tp >= entry:
        return None

    return {
        "signal": sig,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "pattern": f"ท่าที่ 62 AllIn4S_CloseCover_{sig}",
        "reason": (
            f"All-in-4S close-cover reversal bodyATR={body/atr:.2f} "
            f"bodyRatio={body/rng:.2f} {level_reason}"
        ),
        "order_mode": "market",
        "signal_bar_time": int(cur["time"]),
        "atr_at_signal": atr,
    }


def detect_s62(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    if rates is None or len(rates) < 80:
        return {"signal": "WAIT", "reason": "S62: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S62: นอก session"}
    closed = rates[:-1]
    found = _detect_closed(closed, len(closed) - 1, cfg or S62_DEFAULTS)
    if found is None:
        return {"signal": "WAIT", "reason": "S62: ยังไม่ครบ close-cover + level"}
    return found


def strategy_62(rates, tf: str = "", cfg: dict | None = None):
    return detect_s62(rates, tf=tf, dt_bkk=None, cfg=cfg)
