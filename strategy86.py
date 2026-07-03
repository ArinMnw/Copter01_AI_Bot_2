"""
strategy86.py - S86 All-in-4S Fibo 50-60 RUN Decision.

RESEARCH/BACKTEST-ONLY. Standalone only; not wired into live bot.

Computable idea from All-in-4S notes:
- Fibo 50-60 is a decision area before RUN
- if price tests 50 and does not break structure, it can run
- if it breaks 50 structure, it can return to old H/L
"""

S86_DEFAULTS = {
    "ENTRY_TF": "M5",
    "LOOKBACK": 72,
    "PIVOT_LEFT": 2,
    "PIVOT_RIGHT": 2,
    "IMPULSE_MIN_ATR": 2.2,
    "ZONE_LOW": 0.50,
    "ZONE_HIGH": 0.60,
    "ZONE_TOL_ATR": 0.08,
    "CONFIRM_BODY_ATR": 0.12,
    "CONFIRM_BODY_RATIO": 0.30,
    "RECLAIM_LEVEL": 0.50,
    "REQUIRE_TREND": True,
    "TREND_LOOKBACK": 16,
    "TREND_MIN_ATR": 0.8,
    "SL_MODE": "swing",          # swing | zone
    "SL_ATR_MULT": 0.25,
    "TP_MODE": "old",            # old | rr
    "TP_RR": 1.20,
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
    return S86_DEFAULTS[key]


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


def _trend_ok(closed, j, sig, atr, cfg):
    if not _cfg(cfg, "REQUIRE_TREND"):
        return True
    lb = int(_cfg(cfg, "TREND_LOOKBACK"))
    if j < lb:
        return False
    move = float(closed[j]["close"]) - float(closed[j - lb]["close"])
    if abs(move) < float(_cfg(cfg, "TREND_MIN_ATR")) * atr:
        return False
    return (sig == "BUY" and move > 0) or (sig == "SELL" and move < 0)


def _find_impulse(closed, j, atr, cfg):
    start = max(0, j - int(_cfg(cfg, "LOOKBACK")))
    lows, highs = _pivots(closed, start, j - 2, int(_cfg(cfg, "PIVOT_LEFT")), int(_cfg(cfg, "PIVOT_RIGHT")))
    best = None
    min_imp = float(_cfg(cfg, "IMPULSE_MIN_ATR")) * atr
    for li, lp in lows:
        later_highs = [(hi, hp) for hi, hp in highs if hi > li]
        if later_highs:
            hi, hp = max(later_highs, key=lambda x: x[1] - lp)
            if hp - lp >= min_imp:
                cand = {"dir": "BUY", "lo_idx": li, "hi_idx": hi, "low": lp, "high": hp}
                if best is None or cand["hi_idx"] > best.get("hi_idx", -1):
                    best = cand
    for hi, hp in highs:
        later_lows = [(li, lp) for li, lp in lows if li > hi]
        if later_lows:
            li, lp = min(later_lows, key=lambda x: x[1] - hp)
            if hp - lp >= min_imp:
                cand = {"dir": "SELL", "lo_idx": li, "hi_idx": hi, "low": lp, "high": hp}
                if best is None or cand["lo_idx"] > best.get("lo_idx", -1):
                    best = cand
    return best


def _fib_price(imp, ratio):
    if imp["dir"] == "BUY":
        return imp["high"] - (imp["high"] - imp["low"]) * ratio
    return imp["low"] + (imp["high"] - imp["low"]) * ratio


def _detect_closed(closed, j, cfg, atr_value=None):
    if j < int(_cfg(cfg, "LOOKBACK")) + 20:
        return None
    atr = atr_value if atr_value is not None else _atr(closed[max(0, j - 120):j + 1], 14)
    if atr <= 0:
        return None
    imp = _find_impulse(closed, j, atr, cfg)
    if imp is None:
        return None
    cur = closed[j]
    body = _body(cur)
    rng = _range(cur)
    if body < float(_cfg(cfg, "CONFIRM_BODY_ATR")) * atr or body / rng < float(_cfg(cfg, "CONFIRM_BODY_RATIO")):
        return None
    zone_a = _fib_price(imp, float(_cfg(cfg, "ZONE_LOW")))
    zone_b = _fib_price(imp, float(_cfg(cfg, "ZONE_HIGH")))
    zlo, zhi = min(zone_a, zone_b), max(zone_a, zone_b)
    tol = float(_cfg(cfg, "ZONE_TOL_ATR")) * atr
    reclaim = _fib_price(imp, float(_cfg(cfg, "RECLAIM_LEVEL")))
    sig = imp["dir"]
    if sig == "BUY":
        tested = float(cur["low"]) <= zhi + tol and float(cur["high"]) >= zlo - tol
        ok = tested and _bull(cur) and float(cur["close"]) > reclaim and float(cur["low"]) > imp["low"] - tol
    else:
        tested = float(cur["high"]) >= zlo - tol and float(cur["low"]) <= zhi + tol
        ok = tested and _bear(cur) and float(cur["close"]) < reclaim and float(cur["high"]) < imp["high"] + tol
    if not ok or not _trend_ok(closed, j, sig, atr, cfg):
        return None
    return _make_result(sig, cur, imp, zlo, zhi, atr, cfg)


def _make_result(sig, cur, imp, zlo, zhi, atr, cfg):
    entry = round(float(cur["close"]), 2)
    sl_buf = float(_cfg(cfg, "SL_ATR_MULT")) * atr
    if sig == "BUY":
        base_sl = imp["low"] if _cfg(cfg, "SL_MODE") == "swing" else zlo
        sl = round(min(base_sl, float(cur["low"])) - sl_buf, 2)
        risk = entry - sl
        tp = round(imp["high"], 2) if _cfg(cfg, "TP_MODE") == "old" else round(entry + float(_cfg(cfg, "TP_RR")) * risk, 2)
        if tp <= entry:
            tp = round(entry + float(_cfg(cfg, "TP_RR")) * risk, 2)
    else:
        base_sl = imp["high"] if _cfg(cfg, "SL_MODE") == "swing" else zhi
        sl = round(max(base_sl, float(cur["high"])) + sl_buf, 2)
        risk = sl - entry
        tp = round(imp["low"], 2) if _cfg(cfg, "TP_MODE") == "old" else round(entry - float(_cfg(cfg, "TP_RR")) * risk, 2)
        if tp >= entry:
            tp = round(entry - float(_cfg(cfg, "TP_RR")) * risk, 2)
    if not (0 < risk <= float(_cfg(cfg, "MAX_RISK_ATR_MULT")) * atr):
        return None
    return {
        "signal": sig,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "pattern": f"ท่าที่ 86 AllIn4S_Fibo50_RUN_{sig}",
        "reason": (
            f"fiboRUN imp={imp['lo_idx']}/{imp['hi_idx']} zone={zlo:.2f}-{zhi:.2f} "
            f"riskATR={risk/atr:.2f}"
        ),
        "order_mode": "market",
        "signal_bar_time": int(cur["time"]),
        "atr_at_signal": atr,
    }


def detect_s86(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    if rates is None or len(rates) < 130:
        return {"signal": "WAIT", "reason": "S86: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S86: นอก session"}
    closed = rates[:-1]
    found = _detect_closed(closed, len(closed) - 1, cfg or S86_DEFAULTS)
    if found is None:
        return {"signal": "WAIT", "reason": "S86: ยังไม่ครบ Fibo 50 RUN"}
    return found


def strategy_86(rates, tf: str = "", cfg: dict | None = None):
    return detect_s86(rates, tf=tf, dt_bkk=None, cfg=cfg)
