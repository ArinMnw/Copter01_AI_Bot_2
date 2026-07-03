"""
strategy85.py - S85 All-in-4S Significant Level Rejection.

RESEARCH/BACKTEST-ONLY. Standalone only; not wired into live bot.

Computable idea from All-in-4S notes:
- important levels come from old H/L breaks, first rejection wick,
  old support/resistance, doji/significant candle, and psychological numbers
- wait for price to revisit a recent significant level and reject on a closed bar
"""

S85_DEFAULTS = {
    "ENTRY_TF": "M5",
    "LOOKBACK": 96,
    "PIVOT_LEFT": 2,
    "PIVOT_RIGHT": 2,
    "MIN_LEVEL_AGE": 6,
    "TOUCH_TOL_ATR": 0.12,
    "CLOSE_AWAY_ATR": 0.06,
    "MIN_REJECT_WICK_ATR": 0.18,
    "WICK_BODY_MULT": 0.8,
    "MIN_BODY_ATR": 0.06,
    "MIN_RANGE_ATR": 0.35,
    "DOJI_BODY_RATIO": 0.20,
    "USE_DOJI_LEVELS": True,
    "USE_PIVOT_LEVELS": True,
    "REQUIRE_TREND_INTO_LEVEL": True,
    "TREND_LOOKBACK": 12,
    "TREND_MIN_ATR": 0.7,
    "SL_ATR_MULT": 0.25,
    "TP_RR": 1.20,
    "MAX_RISK_ATR_MULT": 4.0,
    "MIN_GAP_BARS": 6,
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
    return S85_DEFAULTS[key]


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


def _pivots(closed, start, end, left, right):
    lows, highs = [], []
    for i in range(max(start + left, left), min(end - right, len(closed) - right - 1) + 1):
        win = closed[i - left:i + right + 1]
        lo = float(closed[i]["low"])
        hi = float(closed[i]["high"])
        if lo == min(float(b["low"]) for b in win):
            lows.append((i, lo))
        if hi == max(float(b["high"]) for b in win):
            highs.append((i, hi))
    return lows, highs


def _levels(closed, j, atr, cfg):
    start = max(0, j - int(_cfg(cfg, "LOOKBACK")))
    max_idx = j - int(_cfg(cfg, "MIN_LEVEL_AGE"))
    pre = cfg.get("_PRE_LEVELS") if cfg else None
    if pre is not None:
        levels = [lv for lv in pre if start <= lv["idx"] <= max_idx]
    else:
        levels = []
    if pre is None and _cfg(cfg, "USE_PIVOT_LEVELS"):
        lows, highs = _pivots(
            closed, start, max_idx,
            int(_cfg(cfg, "PIVOT_LEFT")),
            int(_cfg(cfg, "PIVOT_RIGHT")),
        )
        levels += [{"idx": i, "kind": "pivot_high", "side": "RES", "price": p} for i, p in highs]
        levels += [{"idx": i, "kind": "pivot_low", "side": "SUP", "price": p} for i, p in lows]
    if pre is None and _cfg(cfg, "USE_DOJI_LEVELS"):
        for i in range(start, max_idx + 1):
            b = closed[i]
            if _body(b) / _range(b) <= float(_cfg(cfg, "DOJI_BODY_RATIO")):
                levels.append({"idx": i, "kind": "doji_high", "side": "RES", "price": float(b["high"])})
                levels.append({"idx": i, "kind": "doji_low", "side": "SUP", "price": float(b["low"])})
    # Keep only reasonably distinct, most recent levels.
    levels = sorted(levels, key=lambda x: x["idx"], reverse=True)
    deduped = []
    for lv in levels:
        if any(abs(lv["price"] - x["price"]) <= 0.12 * atr and lv["side"] == x["side"] for x in deduped):
            continue
        deduped.append(lv)
        if len(deduped) >= 12:
            break
    return deduped


def _trend_into_level(closed, j, sig, atr, cfg):
    if not _cfg(cfg, "REQUIRE_TREND_INTO_LEVEL"):
        return True
    lb = int(_cfg(cfg, "TREND_LOOKBACK"))
    if j < lb:
        return False
    move = float(closed[j]["close"]) - float(closed[j - lb]["close"])
    if abs(move) < float(_cfg(cfg, "TREND_MIN_ATR")) * atr:
        return False
    # SELL needs price rallying into resistance; BUY needs price dropping into support.
    return (sig == "SELL" and move > 0) or (sig == "BUY" and move < 0)


def _detect_closed(closed, j, cfg, atr_value=None):
    if j < int(_cfg(cfg, "LOOKBACK")) + 20:
        return None
    atr = atr_value if atr_value is not None else _atr(closed[max(0, j - 110):j + 1], 14)
    if atr <= 0:
        return None
    cur = closed[j]
    if _body(cur) < float(_cfg(cfg, "MIN_BODY_ATR")) * atr:
        return None
    if _range(cur) < float(_cfg(cfg, "MIN_RANGE_ATR")) * atr:
        return None

    touch_tol = float(_cfg(cfg, "TOUCH_TOL_ATR")) * atr
    close_away = float(_cfg(cfg, "CLOSE_AWAY_ATR")) * atr
    min_wick = float(_cfg(cfg, "MIN_REJECT_WICK_ATR")) * atr
    wick_mult = float(_cfg(cfg, "WICK_BODY_MULT"))
    body = max(_body(cur), 0.0001)

    for lv in _levels(closed, j, atr, cfg):
        price = lv["price"]
        if lv["side"] == "RES":
            touched = float(cur["high"]) >= price - touch_tol
            rejected = float(cur["close"]) <= price - close_away
            wick_ok = _upper_wick(cur) >= min_wick and _upper_wick(cur) >= wick_mult * body
            if touched and rejected and wick_ok and _bear(cur) and _trend_into_level(closed, j, "SELL", atr, cfg):
                return _make_result("SELL", cur, lv, atr, cfg)
        else:
            touched = float(cur["low"]) <= price + touch_tol
            rejected = float(cur["close"]) >= price + close_away
            wick_ok = _lower_wick(cur) >= min_wick and _lower_wick(cur) >= wick_mult * body
            if touched and rejected and wick_ok and _bull(cur) and _trend_into_level(closed, j, "BUY", atr, cfg):
                return _make_result("BUY", cur, lv, atr, cfg)
    return None


def _make_result(sig, cur, lv, atr, cfg):
    entry = round(float(cur["close"]), 2)
    sl_buf = float(_cfg(cfg, "SL_ATR_MULT")) * atr
    if sig == "SELL":
        sl = round(max(float(cur["high"]), lv["price"]) + sl_buf, 2)
        risk = sl - entry
        tp = round(entry - float(_cfg(cfg, "TP_RR")) * risk, 2)
    else:
        sl = round(min(float(cur["low"]), lv["price"]) - sl_buf, 2)
        risk = entry - sl
        tp = round(entry + float(_cfg(cfg, "TP_RR")) * risk, 2)
    if not (0 < risk <= float(_cfg(cfg, "MAX_RISK_ATR_MULT")) * atr):
        return None
    return {
        "signal": sig,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "pattern": f"ท่าที่ 85 AllIn4S_SignificantLevel_{sig}",
        "reason": (
            f"sigLevel kind={lv['kind']} age={lv['idx']} price={lv['price']:.2f} "
            f"riskATR={risk/atr:.2f}"
        ),
        "order_mode": "market",
        "signal_bar_time": int(cur["time"]),
        "atr_at_signal": atr,
    }


def detect_s85(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    if rates is None or len(rates) < 130:
        return {"signal": "WAIT", "reason": "S85: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S85: นอก session"}
    closed = rates[:-1]
    found = _detect_closed(closed, len(closed) - 1, cfg or S85_DEFAULTS)
    if found is None:
        return {"signal": "WAIT", "reason": "S85: ยังไม่ถึง significant level rejection"}
    return found


def strategy_85(rates, tf: str = "", cfg: dict | None = None):
    return detect_s85(rates, tf=tf, dt_bkk=None, cfg=cfg)
