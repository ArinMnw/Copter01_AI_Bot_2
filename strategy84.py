"""
strategy84.py - S84 All-in-4S Old Wick Eat Close-Fail Revisit.

RESEARCH/BACKTEST-ONLY. Standalone only; not wired into live bot.

Computable idea from All-in-4S notes:
- price eats an old wick but the candle cannot close-cover it
- failed cover implies price may revisit back inside the defect/old wick area
- enter after the closed fail candle, targeting a nearby revisit/mean return
"""

S84_DEFAULTS = {
    "ENTRY_TF": "M5",
    "LOOKBACK": 48,
    "REF_MIN_WICK_ATR": 0.35,
    "REF_WICK_BODY_MULT": 0.8,
    "EAT_TOL_ATR": 0.08,
    "CLOSE_FAIL_ATR": 0.05,
    "REQUIRE_OPPOSITE_CLOSE": True,
    "MIN_BODY_ATR": 0.08,
    "MIN_RANGE_ATR": 0.35,
    "TARGET_MODE": "mid",          # mid | body | rr
    "MODE": "revisit",             # revisit | follow
    "SL_ATR_MULT": 0.25,
    "TP_RR": 1.10,
    "MAX_RISK_ATR_MULT": 4.0,
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
    return S84_DEFAULTS[key]


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


def _wick_refs(closed, start, end, atr, cfg):
    refs = []
    min_wick = float(_cfg(cfg, "REF_MIN_WICK_ATR")) * atr
    wick_mult = float(_cfg(cfg, "REF_WICK_BODY_MULT"))
    for i in range(start, end):
        b = closed[i]
        body = max(_body(b), 0.0001)
        up = _upper_wick(b)
        lo = _lower_wick(b)
        if up >= min_wick and up >= wick_mult * body:
            refs.append({
                "idx": i,
                "side": "UPPER",
                "extreme": float(b["high"]),
                "inner": max(float(b["open"]), float(b["close"])),
                "mid": (float(b["high"]) + max(float(b["open"]), float(b["close"]))) / 2.0,
            })
        if lo >= min_wick and lo >= wick_mult * body:
            refs.append({
                "idx": i,
                "side": "LOWER",
                "extreme": float(b["low"]),
                "inner": min(float(b["open"]), float(b["close"])),
                "mid": (float(b["low"]) + min(float(b["open"]), float(b["close"]))) / 2.0,
            })
    return refs


def _detect_closed(closed, j, cfg, atr_value=None):
    lb = int(_cfg(cfg, "LOOKBACK"))
    if j < lb + 20:
        return None
    atr = atr_value if atr_value is not None else _atr(closed[max(0, j - 90):j + 1], 14)
    if atr <= 0:
        return None
    cur = closed[j]
    if _body(cur) < float(_cfg(cfg, "MIN_BODY_ATR")) * atr:
        return None
    if _range(cur) < float(_cfg(cfg, "MIN_RANGE_ATR")) * atr:
        return None

    start = max(0, j - lb)
    refs = _wick_refs(closed, start, j - 1, atr, cfg)
    if not refs:
        return None
    eat_tol = float(_cfg(cfg, "EAT_TOL_ATR")) * atr
    fail = float(_cfg(cfg, "CLOSE_FAIL_ATR")) * atr

    # Use nearest/latest valid reference to reduce stale level overfitting.
    refs = sorted(refs, key=lambda r: r["idx"], reverse=True)
    for ref in refs:
        if ref["side"] == "UPPER":
            ate = float(cur["high"]) >= ref["extreme"] - eat_tol
            failed_cover = float(cur["close"]) <= ref["extreme"] - fail
            opposite = (not _cfg(cfg, "REQUIRE_OPPOSITE_CLOSE")) or _bear(cur)
            if ate and failed_cover and opposite:
                if _cfg(cfg, "MODE") == "follow":
                    return _make_follow_result("BUY", cur, ref, atr, cfg)
                return _make_result("SELL", cur, ref, atr, cfg)
        else:
            ate = float(cur["low"]) <= ref["extreme"] + eat_tol
            failed_cover = float(cur["close"]) >= ref["extreme"] + fail
            opposite = (not _cfg(cfg, "REQUIRE_OPPOSITE_CLOSE")) or _bull(cur)
            if ate and failed_cover and opposite:
                if _cfg(cfg, "MODE") == "follow":
                    return _make_follow_result("SELL", cur, ref, atr, cfg)
                return _make_result("BUY", cur, ref, atr, cfg)
    return None


def _make_result(sig, cur, ref, atr, cfg):
    entry = round(float(cur["close"]), 2)
    sl_buf = float(_cfg(cfg, "SL_ATR_MULT")) * atr
    target_mode = _cfg(cfg, "TARGET_MODE")
    if sig == "SELL":
        sl = round(max(float(cur["high"]), ref["extreme"]) + sl_buf, 2)
        risk = sl - entry
        if target_mode == "body":
            tp = round(ref["inner"], 2)
        elif target_mode == "mid":
            tp = round(min(ref["mid"], entry - float(_cfg(cfg, "TP_RR")) * risk), 2)
        else:
            tp = round(entry - float(_cfg(cfg, "TP_RR")) * risk, 2)
        if tp >= entry:
            tp = round(entry - float(_cfg(cfg, "TP_RR")) * risk, 2)
    else:
        sl = round(min(float(cur["low"]), ref["extreme"]) - sl_buf, 2)
        risk = entry - sl
        if target_mode == "body":
            tp = round(ref["inner"], 2)
        elif target_mode == "mid":
            tp = round(max(ref["mid"], entry + float(_cfg(cfg, "TP_RR")) * risk), 2)
        else:
            tp = round(entry + float(_cfg(cfg, "TP_RR")) * risk, 2)
        if tp <= entry:
            tp = round(entry + float(_cfg(cfg, "TP_RR")) * risk, 2)
    if not (0 < risk <= float(_cfg(cfg, "MAX_RISK_ATR_MULT")) * atr):
        return None
    return {
        "signal": sig,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "pattern": f"ท่าที่ 84 AllIn4S_OldWick_CloseFail_{sig}",
        "reason": (
            f"oldWick side={ref['side']} ageRef={ref['idx']} mode={target_mode} "
            f"riskATR={risk/atr:.2f}"
        ),
        "order_mode": "market",
        "signal_bar_time": int(cur["time"]),
        "atr_at_signal": atr,
    }


def _make_follow_result(sig, cur, ref, atr, cfg):
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
        "pattern": f"ท่าที่ 84 AllIn4S_OldWick_Follow_{sig}",
        "reason": (
            f"oldWickFollow side={ref['side']} ageRef={ref['idx']} "
            f"riskATR={risk/atr:.2f}"
        ),
        "order_mode": "market",
        "signal_bar_time": int(cur["time"]),
        "atr_at_signal": atr,
    }


def detect_s84(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    if rates is None or len(rates) < 100:
        return {"signal": "WAIT", "reason": "S84: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S84: นอก session"}
    closed = rates[:-1]
    found = _detect_closed(closed, len(closed) - 1, cfg or S84_DEFAULTS)
    if found is None:
        return {"signal": "WAIT", "reason": "S84: ยังไม่ครบ old wick close-fail"}
    return found


def strategy_84(rates, tf: str = "", cfg: dict | None = None):
    return detect_s84(rates, tf=tf, dt_bkk=None, cfg=cfg)
