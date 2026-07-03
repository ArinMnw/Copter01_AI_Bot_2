"""
strategy65.py - S65 All-in-4S Fake Reversal Trap, RESEARCH/BACKTEST-ONLY.

Standalone only: not imported by scanner.py/trailing.py/main.py.

Computable idea from All-in-4S notes:
- price forms a directional H-L leg
- a counter-move creates a fake reversal/pullback
- the fake move fails to break the leg reference
- enter back in the original leg direction on a closed-bar reclaim
"""

S65_DEFAULTS = {
    "ENTRY_TF": "M5",
    "LEG_LOOKBACK": 18,
    "PULLBACK_BARS": 4,
    "LEG_MIN_ATR": 1.2,
    "PULLBACK_MIN_ATR": 0.35,
    "FAIL_TOL_ATR": 0.15,
    "CONFIRM_BODY_ATR": 0.18,
    "CONFIRM_BODY_RATIO": 0.35,
    "SL_ATR_MULT": 0.35,
    "TP_RR": 1.25,
    "FLIP_SIGNAL": False,
    "MAX_RISK_ATR_MULT": 5.0,
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
    return S65_DEFAULTS[key]


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


def _detect_closed(closed, j, cfg, atr_value=None):
    leg_lb = int(_cfg(cfg, "LEG_LOOKBACK"))
    pb = int(_cfg(cfg, "PULLBACK_BARS"))
    if j < leg_lb + pb + 20:
        return None
    atr = atr_value if atr_value is not None else _atr(closed[max(0, j - 80):j + 1], 14)
    if atr <= 0:
        return None

    cur = closed[j]
    body = _body(cur)
    if body < float(_cfg(cfg, "CONFIRM_BODY_ATR")) * atr:
        return None
    if body / _range(cur) < float(_cfg(cfg, "CONFIRM_BODY_RATIO")):
        return None

    leg = closed[j - pb - leg_lb:j - pb]
    fake = closed[j - pb:j]
    if len(leg) < leg_lb or len(fake) < pb:
        return None

    leg_first = float(leg[0]["close"])
    leg_last = float(leg[-1]["close"])
    leg_move = leg_last - leg_first
    if abs(leg_move) < float(_cfg(cfg, "LEG_MIN_ATR")) * atr:
        return None

    tol = float(_cfg(cfg, "FAIL_TOL_ATR")) * atr
    fake_high = max(float(b["high"]) for b in fake)
    fake_low = min(float(b["low"]) for b in fake)
    fake_open = float(fake[0]["open"])
    fake_close = float(fake[-1]["close"])
    fake_move = fake_close - fake_open
    leg_high = max(float(b["high"]) for b in leg)
    leg_low = min(float(b["low"]) for b in leg)

    sig = None
    if leg_move > 0:
        pullback = fake_open - fake_close
        failed_break = fake_low > leg_low - tol
        reclaim = _bull(cur) and float(cur["close"]) > max(float(b["open"]) for b in fake)
        if pullback >= float(_cfg(cfg, "PULLBACK_MIN_ATR")) * atr and failed_break and reclaim:
            sig = "BUY"
    else:
        pullback = fake_close - fake_open
        failed_break = fake_high < leg_high + tol
        reclaim = _bear(cur) and float(cur["close"]) < min(float(b["open"]) for b in fake)
        if pullback >= float(_cfg(cfg, "PULLBACK_MIN_ATR")) * atr and failed_break and reclaim:
            sig = "SELL"

    if sig is None:
        return None

    if _cfg(cfg, "FLIP_SIGNAL"):
        sig = "SELL" if sig == "BUY" else "BUY"

    entry = round(float(cur["close"]), 2)
    sl_buf = float(_cfg(cfg, "SL_ATR_MULT")) * atr
    if sig == "BUY":
        sl = round(min(fake_low, float(cur["low"])) - sl_buf, 2)
        risk = entry - sl
        tp = round(entry + float(_cfg(cfg, "TP_RR")) * risk, 2)
    else:
        sl = round(max(fake_high, float(cur["high"])) + sl_buf, 2)
        risk = sl - entry
        tp = round(entry - float(_cfg(cfg, "TP_RR")) * risk, 2)
    if not (0 < risk <= float(_cfg(cfg, "MAX_RISK_ATR_MULT")) * atr):
        return None

    return {
        "signal": sig,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "pattern": f"ท่าที่ 65 AllIn4S_FakeReversalTrap_{sig}",
        "reason": (
            f"fakeTrap legATR={abs(leg_move)/atr:.2f} pullATR={abs(fake_move)/atr:.2f} "
            f"pb={pb} riskATR={risk/atr:.2f}"
        ),
        "order_mode": "market",
        "signal_bar_time": int(cur["time"]),
        "atr_at_signal": atr,
    }


def detect_s65(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    if rates is None or len(rates) < 100:
        return {"signal": "WAIT", "reason": "S65: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S65: นอก session"}
    closed = rates[:-1]
    found = _detect_closed(closed, len(closed) - 1, cfg or S65_DEFAULTS)
    if found is None:
        return {"signal": "WAIT", "reason": "S65: ยังไม่ครบ fake reversal trap"}
    return found


def strategy_65(rates, tf: str = "", cfg: dict | None = None):
    return detect_s65(rates, tf=tf, dt_bkk=None, cfg=cfg)
