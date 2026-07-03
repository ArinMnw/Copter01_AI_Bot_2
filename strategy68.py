"""
strategy68.py - S68 All-in-4S 2L/2H Fail-to-Break, RESEARCH/BACKTEST-ONLY

Standalone only: not imported by scanner.py/trailing.py/main.py.

Computable idea from All-in-4S 2L/2H notes:
- 2L/2H is not enough by itself
- after 2L, failure to break the prior H can become a sell reversal
- after 2H, failure to break the prior L can become a buy reversal
- use base FVG context and clear-candle confirmation as filters
"""

S68_DEFAULTS = {
    "ENTRY_TF": "M5",
    "LOOKBACK": 72,
    "PIVOT_LEFT": 2,
    "PIVOT_RIGHT": 2,
    "DOUBLE_TOL_ATR": 0.35,
    "FAIL_TOL_ATR": 0.15,
    "MIN_SWING_ATR": 1.8,
    "REQUIRE_CLEAR": True,
    "CLEAR_WICK_BODY_MULT": 0.8,
    "CLEAR_CLOSE": "body",          # body | wick
    "REQUIRE_BASE_FVG": True,
    "FVG_MIN_ATR": 0.04,
    "FVG_LOOKBACK": 80,
    "FVG_TOUCH_TOL_ATR": 0.20,
    "MIN_BODY_ATR": 0.12,
    "MIN_BODY_RATIO": 0.30,
    "SL_ATR_MULT": 0.30,
    "TP_RR": 1.35,
    "MAX_RISK_ATR_MULT": 5.0,
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
    return S68_DEFAULTS[key]


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


def _base_fvg_ok(closed, j, sig, atr, cfg):
    if not _cfg(cfg, "REQUIRE_BASE_FVG"):
        return True
    start = max(2, j - int(_cfg(cfg, "FVG_LOOKBACK")))
    min_gap = float(_cfg(cfg, "FVG_MIN_ATR")) * atr
    fvgs = []
    for i in range(start, j):
        b0 = closed[i - 2]
        b2 = closed[i]
        if sig == "BUY" and float(b2["low"]) > float(b0["high"]) + min_gap:
            fvgs.append({"low": float(b0["high"]), "high": float(b2["low"]), "idx": i})
        elif sig == "SELL" and float(b2["high"]) < float(b0["low"]) - min_gap:
            fvgs.append({"low": float(b2["high"]), "high": float(b0["low"]), "idx": i})
    if not fvgs:
        return False
    zone = fvgs[0]
    tol = float(_cfg(cfg, "FVG_TOUCH_TOL_ATR")) * atr
    cur = closed[j]
    return float(cur["low"]) <= zone["high"] + tol and float(cur["high"]) >= zone["low"] - tol


def _clear_ok(closed, j, sig, atr, cfg):
    if not _cfg(cfg, "REQUIRE_CLEAR"):
        return True
    cur = closed[j]
    prev = closed[j - 1]
    body = _body(cur)
    if sig == "BUY":
        wick = _lower_wick(cur)
        ok = _bull(cur) and wick >= float(_cfg(cfg, "CLEAR_WICK_BODY_MULT")) * max(body, 0.0001)
        if _cfg(cfg, "CLEAR_CLOSE") == "wick":
            ok = ok and float(cur["close"]) > float(prev["high"])
        else:
            ok = ok and float(cur["close"]) > max(float(prev["open"]), float(prev["close"]))
    else:
        wick = _upper_wick(cur)
        ok = _bear(cur) and wick >= float(_cfg(cfg, "CLEAR_WICK_BODY_MULT")) * max(body, 0.0001)
        if _cfg(cfg, "CLEAR_CLOSE") == "wick":
            ok = ok and float(cur["close"]) < float(prev["low"])
        else:
            ok = ok and float(cur["close"]) < min(float(prev["open"]), float(prev["close"]))
    return ok


def _detect_closed(closed, j, cfg, atr_value=None):
    if j < int(_cfg(cfg, "LOOKBACK")) + 5:
        return None
    atr = atr_value if atr_value is not None else _atr(closed[max(0, j - 100):j + 1], 14)
    if atr <= 0:
        return None
    cur = closed[j]
    body = _body(cur)
    rng = _range(cur)
    if body < float(_cfg(cfg, "MIN_BODY_ATR")) * atr or body / rng < float(_cfg(cfg, "MIN_BODY_RATIO")):
        return None

    start = max(0, j - int(_cfg(cfg, "LOOKBACK")))
    lows, highs = _pivots(closed, start, j - 1, int(_cfg(cfg, "PIVOT_LEFT")), int(_cfg(cfg, "PIVOT_RIGHT")))
    if len(lows) < 2 or len(highs) < 1:
        return None
    tol = float(_cfg(cfg, "DOUBLE_TOL_ATR")) * atr
    fail_tol = float(_cfg(cfg, "FAIL_TOL_ATR")) * atr
    min_swing = float(_cfg(cfg, "MIN_SWING_ATR")) * atr

    # 2L fails to break the prior H -> SELL.
    l1, l2 = lows[-2], lows[-1]
    prior_highs = [h for h in highs if l1[0] < h[0] < l2[0]]
    if prior_highs and abs(l2[1] - l1[1]) <= tol:
        ph = max(prior_highs, key=lambda x: x[1])
        if ph[1] - min(l1[1], l2[1]) >= min_swing:
            failed_h = max(float(b["high"]) for b in closed[l2[0]:j + 1]) <= ph[1] + fail_tol
            trigger = _bear(cur) and float(cur["close"]) < min(float(closed[l2[0]]["low"]), float(closed[j - 1]["low"]))
            if failed_h and trigger and _clear_ok(closed, j, "SELL", atr, cfg) and _base_fvg_ok(closed, j, "SELL", atr, cfg):
                entry = round(float(cur["close"]), 2)
                sl = round(max(ph[1], float(cur["high"])) + float(_cfg(cfg, "SL_ATR_MULT")) * atr, 2)
                risk = sl - entry
                if 0 < risk <= float(_cfg(cfg, "MAX_RISK_ATR_MULT")) * atr:
                    return _result("SELL", entry, sl, round(entry - float(_cfg(cfg, "TP_RR")) * risk, 2), risk, atr, cur, "2L_fail_H")

    # 2H fails to break the prior L -> BUY.
    if len(highs) >= 2 and len(lows) >= 1:
        h1, h2 = highs[-2], highs[-1]
        prior_lows = [l for l in lows if h1[0] < l[0] < h2[0]]
        if prior_lows and abs(h2[1] - h1[1]) <= tol:
            pl = min(prior_lows, key=lambda x: x[1])
            if max(h1[1], h2[1]) - pl[1] >= min_swing:
                failed_l = min(float(b["low"]) for b in closed[h2[0]:j + 1]) >= pl[1] - fail_tol
                trigger = _bull(cur) and float(cur["close"]) > max(float(closed[h2[0]]["high"]), float(closed[j - 1]["high"]))
                if failed_l and trigger and _clear_ok(closed, j, "BUY", atr, cfg) and _base_fvg_ok(closed, j, "BUY", atr, cfg):
                    entry = round(float(cur["close"]), 2)
                    sl = round(min(pl[1], float(cur["low"])) - float(_cfg(cfg, "SL_ATR_MULT")) * atr, 2)
                    risk = entry - sl
                    if 0 < risk <= float(_cfg(cfg, "MAX_RISK_ATR_MULT")) * atr:
                        return _result("BUY", entry, sl, round(entry + float(_cfg(cfg, "TP_RR")) * risk, 2), risk, atr, cur, "2H_fail_L")
    return None


def _result(sig, entry, sl, tp, risk, atr, cur, setup):
    return {
        "signal": sig,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "pattern": f"ท่าที่ 68 AllIn4S_2L2H_Fail_{sig}",
        "reason": f"{setup} clear+baseFVG riskATR={risk/atr:.2f}",
        "order_mode": "market",
        "signal_bar_time": int(cur["time"]),
        "atr_at_signal": atr,
    }


def detect_s68(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    if rates is None or len(rates) < 120:
        return {"signal": "WAIT", "reason": "S68: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S68: นอก session"}
    closed = rates[:-1]
    found = _detect_closed(closed, len(closed) - 1, cfg or S68_DEFAULTS)
    if found is None:
        return {"signal": "WAIT", "reason": "S68: ยังไม่ครบ 2L/2H fail-to-break"}
    return found


def strategy_68(rates, tf: str = "", cfg: dict | None = None):
    return detect_s68(rates, tf=tf, dt_bkk=None, cfg=cfg)
