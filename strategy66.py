"""
strategy66.py - S66 All-in-4S FVG Ladder Follow Trend, RESEARCH/BACKTEST-ONLY

Standalone only: not imported by scanner.py/trailing.py/main.py.

Computable idea from All-in-4S Follow Trend notes:
- a real trend often leaves a ladder of FVGs
- the newest FVG failing to create a new H/L warns of deeper pullback
- the base/lower FVG can be a stronger trend-continuation decision zone
"""

S66_DEFAULTS = {
    "ENTRY_TF": "M5",
    "LOOKBACK": 80,
    "FVG_MIN_ATR": 0.04,
    "MIN_FVG_COUNT": 3,
    "ZONE_SELECT": "base",          # base | middle | latest
    "TOUCH_TOL_ATR": 0.10,
    "MIN_BODY_ATR": 0.18,
    "MIN_BODY_RATIO": 0.35,
    "CLOSE_BEYOND_ZONE": True,
    "REQUIRE_LATEST_FAIL": False,
    "FAIL_LOOKAHEAD": 8,
    "SL_ATR_MULT": 0.40,
    "TP_RR": 1.25,
    "MAX_RISK_ATR_MULT": 5.0,
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
    return S66_DEFAULTS[key]


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


def _fvg_ladder(closed, start, end, atr, cfg):
    min_gap = float(_cfg(cfg, "FVG_MIN_ATR")) * atr
    bull = []
    bear = []
    for i in range(max(start + 2, 2), end + 1):
        b0 = closed[i - 2]
        b2 = closed[i]
        if float(b2["low"]) > float(b0["high"]) + min_gap:
            bull.append({
                "idx": i,
                "low": float(b0["high"]),
                "high": float(b2["low"]),
                "gap": float(b2["low"]) - float(b0["high"]),
                "extreme": float(b2["high"]),
            })
        if float(b2["high"]) < float(b0["low"]) - min_gap:
            bear.append({
                "idx": i,
                "low": float(b2["high"]),
                "high": float(b0["low"]),
                "gap": float(b0["low"]) - float(b2["high"]),
                "extreme": float(b2["low"]),
            })
    return bull, bear


def _select_zone(fvgs, cfg):
    if not fvgs:
        return None
    mode = _cfg(cfg, "ZONE_SELECT")
    if mode == "latest":
        return fvgs[-1]
    if mode == "middle":
        return fvgs[len(fvgs) // 2]
    return fvgs[0]


def _latest_fvg_failed(closed, fvgs, direction, cfg):
    if not fvgs:
        return False
    latest = fvgs[-1]
    start = latest["idx"] + 1
    end = min(len(closed) - 1, latest["idx"] + int(_cfg(cfg, "FAIL_LOOKAHEAD")))
    if start > end:
        return False
    post = closed[start:end + 1]
    if direction == "BUY":
        made_new = max(float(b["high"]) for b in post) > latest["extreme"]
        touched = min(float(b["low"]) for b in post) <= latest["high"]
    else:
        made_new = min(float(b["low"]) for b in post) < latest["extreme"]
        touched = max(float(b["high"]) for b in post) >= latest["low"]
    return touched and not made_new


def _detect_closed(closed, j, cfg, atr_value=None):
    if j < int(_cfg(cfg, "LOOKBACK")) + 5:
        return None
    atr = atr_value if atr_value is not None else _atr(closed[max(0, j - 100):j + 1], 14)
    if atr <= 0:
        return None
    cur = closed[j]
    body = _body(cur)
    rng = _range(cur)
    if body < float(_cfg(cfg, "MIN_BODY_ATR")) * atr:
        return None
    if body / rng < float(_cfg(cfg, "MIN_BODY_RATIO")):
        return None

    start = max(0, j - int(_cfg(cfg, "LOOKBACK")))
    bull_fvgs, bear_fvgs = _fvg_ladder(closed, start, j - 1, atr, cfg)
    min_count = int(_cfg(cfg, "MIN_FVG_COUNT"))
    candidates = []
    if len(bull_fvgs) >= min_count:
        candidates.append(("BUY", bull_fvgs))
    if len(bear_fvgs) >= min_count:
        candidates.append(("SELL", bear_fvgs))
    if not candidates:
        return None

    tol = float(_cfg(cfg, "TOUCH_TOL_ATR")) * atr
    for sig, fvgs in candidates:
        zone = _select_zone(fvgs, cfg)
        if zone is None:
            continue
        if _cfg(cfg, "REQUIRE_LATEST_FAIL") and not _latest_fvg_failed(closed[:j + 1], fvgs, sig, cfg):
            continue
        if sig == "BUY":
            touched = float(cur["low"]) <= zone["high"] + tol and float(cur["high"]) >= zone["low"] - tol
            close_ok = _bull(cur) and (not _cfg(cfg, "CLOSE_BEYOND_ZONE") or float(cur["close"]) > zone["high"])
            if not (touched and close_ok):
                continue
            entry = round(float(cur["close"]), 2)
            sl = round(min(float(cur["low"]), zone["low"]) - float(_cfg(cfg, "SL_ATR_MULT")) * atr, 2)
            risk = entry - sl
            tp = round(entry + float(_cfg(cfg, "TP_RR")) * risk, 2)
        else:
            touched = float(cur["high"]) >= zone["low"] - tol and float(cur["low"]) <= zone["high"] + tol
            close_ok = _bear(cur) and (not _cfg(cfg, "CLOSE_BEYOND_ZONE") or float(cur["close"]) < zone["low"])
            if not (touched and close_ok):
                continue
            entry = round(float(cur["close"]), 2)
            sl = round(max(float(cur["high"]), zone["high"]) + float(_cfg(cfg, "SL_ATR_MULT")) * atr, 2)
            risk = sl - entry
            tp = round(entry - float(_cfg(cfg, "TP_RR")) * risk, 2)
        if not (0 < risk <= float(_cfg(cfg, "MAX_RISK_ATR_MULT")) * atr):
            continue
        return {
            "signal": sig,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "pattern": f"ท่าที่ 66 AllIn4S_FVG_Ladder_{sig}",
            "reason": (
                f"FVG ladder count={len(fvgs)} select={_cfg(cfg, 'ZONE_SELECT')} "
                f"zone={zone['idx']} gapATR={zone['gap']/atr:.2f} riskATR={risk/atr:.2f}"
            ),
            "order_mode": "market",
            "signal_bar_time": int(cur["time"]),
            "atr_at_signal": atr,
            "zone_idx": zone["idx"],
        }
    return None


def detect_s66(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    if rates is None or len(rates) < 110:
        return {"signal": "WAIT", "reason": "S66: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S66: นอก session"}
    closed = rates[:-1]
    found = _detect_closed(closed, len(closed) - 1, cfg or S66_DEFAULTS)
    if found is None:
        return {"signal": "WAIT", "reason": "S66: ยังไม่ครบ FVG ladder"}
    return found


def strategy_66(rates, tf: str = "", cfg: dict | None = None):
    return detect_s66(rates, tf=tf, dt_bkk=None, cfg=cfg)
