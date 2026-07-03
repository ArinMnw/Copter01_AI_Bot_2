"""
strategy64.py - S64 All-in-4S KRH Fibo Expansion Hold, RESEARCH/BACKTEST-ONLY

Standalone only: not imported by scanner.py/trailing.py/main.py.

Computable idea from All-in-4S fibo pages:
- find a moderate engulf/defect seed candle pair
- project custom fibo expansion levels 1.617, 3.097, 5.165, 7.044
- trade when price holds/breaks the KRH2/KRH3 decision zone
"""

S64_DEFAULTS = {
    "ENTRY_TF": "M5",
    "SEED_LOOKBACK": 36,
    "SEED_MIN_BODY_ATR": 0.25,
    "SEED_MAX_BODY_ATR": 1.80,
    "SEED_MAX_RANGE_ATR": 2.80,
    "LEVEL": 3.097,                 # 1.617 | 3.097 | 5.165
    "TARGET_LEVEL": 5.165,          # next KRH level
    "LEVEL_TOL_ATR": 0.30,
    "MODE": "hold",                # hold | break
    "MIN_BODY_ATR": 0.18,
    "MIN_BODY_RATIO": 0.35,
    "SL_LEVEL": 1.617,
    "SL_ATR_MULT": 0.20,
    "TP_MODE": "krh",              # krh | rr
    "TP_RR": 1.20,
    "MAX_RISK_ATR_MULT": 6.0,
    "MIN_GAP_BARS": 5,
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
    return S64_DEFAULTS[key]


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


def _find_seed(closed, j, atr, cfg):
    lb = int(_cfg(cfg, "SEED_LOOKBACK"))
    start = max(2, j - lb)
    min_body = float(_cfg(cfg, "SEED_MIN_BODY_ATR")) * atr
    max_body = float(_cfg(cfg, "SEED_MAX_BODY_ATR")) * atr
    max_range = float(_cfg(cfg, "SEED_MAX_RANGE_ATR")) * atr
    for k in range(j - 3, start, -1):
        prev = closed[k - 1]
        cur = closed[k]
        body = _body(cur)
        pair_low = min(float(prev["low"]), float(cur["low"]))
        pair_high = max(float(prev["high"]), float(cur["high"]))
        pair_range = pair_high - pair_low
        if not (min_body <= body <= max_body and 0 < pair_range <= max_range):
            continue
        if _bull(cur) and float(cur["close"]) > float(prev["high"]):
            return {"dir": "BUY", "idx": k, "low": pair_low, "high": pair_high, "range": pair_range}
        if _bear(cur) and float(cur["close"]) < float(prev["low"]):
            return {"dir": "SELL", "idx": k, "low": pair_low, "high": pair_high, "range": pair_range}
    return None


def _level(seed, ratio):
    if seed["dir"] == "BUY":
        return seed["low"] + ratio * seed["range"]
    return seed["high"] - ratio * seed["range"]


def _detect_closed(closed, j, cfg, atr_value=None):
    if j < int(_cfg(cfg, "SEED_LOOKBACK")) + 10:
        return None
    atr = atr_value if atr_value is not None else _atr(closed[max(0, j - 80):j + 1], 14)
    if atr <= 0:
        return None
    seed = _find_seed(closed, j, atr, cfg)
    if seed is None:
        return None
    cur = closed[j]
    body = _body(cur)
    rng = _range(cur)
    if body < float(_cfg(cfg, "MIN_BODY_ATR")) * atr:
        return None
    if body / rng < float(_cfg(cfg, "MIN_BODY_RATIO")):
        return None

    lvl = _level(seed, float(_cfg(cfg, "LEVEL")))
    target_lvl = _level(seed, float(_cfg(cfg, "TARGET_LEVEL")))
    sl_lvl = _level(seed, float(_cfg(cfg, "SL_LEVEL")))
    tol = float(_cfg(cfg, "LEVEL_TOL_ATR")) * atr
    mode = _cfg(cfg, "MODE")
    sig = seed["dir"]
    if sig == "BUY":
        if mode == "hold":
            ok = float(cur["low"]) <= lvl + tol and float(cur["close"]) > lvl and _bull(cur)
        else:
            ok = float(cur["close"]) > lvl + tol and _bull(cur)
        if not ok:
            return None
        entry = round(float(cur["close"]), 2)
        sl = round(min(sl_lvl, float(cur["low"])) - float(_cfg(cfg, "SL_ATR_MULT")) * atr, 2)
        risk = entry - sl
        tp = round(target_lvl, 2) if _cfg(cfg, "TP_MODE") == "krh" else round(entry + float(_cfg(cfg, "TP_RR")) * risk, 2)
        if tp <= entry:
            tp = round(entry + float(_cfg(cfg, "TP_RR")) * risk, 2)
    else:
        if mode == "hold":
            ok = float(cur["high"]) >= lvl - tol and float(cur["close"]) < lvl and _bear(cur)
        else:
            ok = float(cur["close"]) < lvl - tol and _bear(cur)
        if not ok:
            return None
        entry = round(float(cur["close"]), 2)
        sl = round(max(sl_lvl, float(cur["high"])) + float(_cfg(cfg, "SL_ATR_MULT")) * atr, 2)
        risk = sl - entry
        tp = round(target_lvl, 2) if _cfg(cfg, "TP_MODE") == "krh" else round(entry - float(_cfg(cfg, "TP_RR")) * risk, 2)
        if tp >= entry:
            tp = round(entry - float(_cfg(cfg, "TP_RR")) * risk, 2)

    if not (0 < risk <= float(_cfg(cfg, "MAX_RISK_ATR_MULT")) * atr):
        return None

    return {
        "signal": sig,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "pattern": f"ท่าที่ 64 AllIn4S_KRH_Fibo_{sig}",
        "reason": (
            f"KRH seed={seed['idx']} level={float(_cfg(cfg, 'LEVEL')):.3f} "
            f"target={float(_cfg(cfg, 'TARGET_LEVEL')):.3f} mode={mode} riskATR={risk/atr:.2f}"
        ),
        "order_mode": "market",
        "signal_bar_time": int(cur["time"]),
        "atr_at_signal": atr,
        "seed_idx": seed["idx"],
    }


def detect_s64(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    if rates is None or len(rates) < 90:
        return {"signal": "WAIT", "reason": "S64: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S64: นอก session"}
    closed = rates[:-1]
    found = _detect_closed(closed, len(closed) - 1, cfg or S64_DEFAULTS)
    if found is None:
        return {"signal": "WAIT", "reason": "S64: ยังไม่ครบ KRH fibo"}
    return found


def strategy_64(rates, tf: str = "", cfg: dict | None = None):
    return detect_s64(rates, tf=tf, dt_bkk=None, cfg=cfg)
