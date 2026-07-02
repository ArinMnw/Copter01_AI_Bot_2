"""
strategy63.py - S63 All-in-4S DMxSP/FVG Reclaim, RESEARCH/BACKTEST-ONLY

Standalone only: not imported by scanner.py/trailing.py/main.py.

Computable idea from All-in-4S DMxSP/FVG pages:
- SP = compact pause/supply-demand box
- price sweeps or breaks the box, then closes back through/away from it
- optional FVG/displacement confirms that the zone is failing to hold price
"""

S63_DEFAULTS = {
    "ENTRY_TF": "M5",
    "SP_LOOKBACK": 12,
    "SP_MAX_ATR": 1.20,
    "MODE": "sweep_reclaim",        # sweep_reclaim | breakout | either
    "SWEEP_LOOKBACK": 3,
    "SWEEP_ATR": 0.05,
    "FVG_REQUIRED": True,
    "FVG_MIN_ATR": 0.03,
    "MIN_BODY_ATR": 0.25,
    "MAX_BODY_ATR": 2.50,
    "MIN_BODY_RATIO": 0.45,
    "SL_ATR_MULT": 0.45,
    "TP_RR": 1.20,
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
    return S63_DEFAULTS[key]


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


def _detect_closed(closed, j, cfg, atr_value=None):
    sp_lb = int(_cfg(cfg, "SP_LOOKBACK"))
    if j < sp_lb + 5:
        return None
    atr = atr_value if atr_value is not None else _atr(closed[max(0, j - 60):j + 1], 14)
    if atr <= 0:
        return None
    cur = closed[j]
    body = _body(cur)
    rng = _range(cur)
    if body < float(_cfg(cfg, "MIN_BODY_ATR")) * atr:
        return None
    if body > float(_cfg(cfg, "MAX_BODY_ATR")) * atr:
        return None
    if body / rng < float(_cfg(cfg, "MIN_BODY_RATIO")):
        return None

    zone_bars = closed[j - sp_lb - 2:j - 2]
    zone_high = max(float(b["high"]) for b in zone_bars)
    zone_low = min(float(b["low"]) for b in zone_bars)
    zone_height = zone_high - zone_low
    if zone_height <= 0 or zone_height > float(_cfg(cfg, "SP_MAX_ATR")) * atr:
        return None

    sweep_lb = int(_cfg(cfg, "SWEEP_LOOKBACK"))
    sweep_bars = closed[max(0, j - sweep_lb):j + 1]
    sweep_buy = min(float(b["low"]) for b in sweep_bars) <= zone_low - float(_cfg(cfg, "SWEEP_ATR")) * atr
    sweep_sell = max(float(b["high"]) for b in sweep_bars) >= zone_high + float(_cfg(cfg, "SWEEP_ATR")) * atr
    breakout_buy = float(cur["close"]) > zone_high
    breakout_sell = float(cur["close"]) < zone_low
    mode = _cfg(cfg, "MODE")

    sig = None
    if _is_bull(cur) and breakout_buy:
        if mode == "breakout" or (mode == "sweep_reclaim" and sweep_buy) or (mode == "either" and (sweep_buy or breakout_buy)):
            sig = "BUY"
    elif _is_bear(cur) and breakout_sell:
        if mode == "breakout" or (mode == "sweep_reclaim" and sweep_sell) or (mode == "either" and (sweep_sell or breakout_sell)):
            sig = "SELL"
    if sig is None:
        return None

    fvg_min = float(_cfg(cfg, "FVG_MIN_ATR")) * atr
    if sig == "BUY":
        fvg = float(cur["low"]) > float(closed[j - 2]["high"]) + fvg_min
    else:
        fvg = float(cur["high"]) < float(closed[j - 2]["low"]) - fvg_min
    if _cfg(cfg, "FVG_REQUIRED") and not fvg:
        return None

    entry = round(float(cur["close"]), 2)
    sl_buf = float(_cfg(cfg, "SL_ATR_MULT")) * atr
    if sig == "BUY":
        sl = round(min(float(cur["low"]), zone_low) - sl_buf, 2)
        risk = entry - sl
        tp = round(entry + float(_cfg(cfg, "TP_RR")) * risk, 2)
    else:
        sl = round(max(float(cur["high"]), zone_high) + sl_buf, 2)
        risk = sl - entry
        tp = round(entry - float(_cfg(cfg, "TP_RR")) * risk, 2)
    if not (0 < risk <= float(_cfg(cfg, "MAX_RISK_ATR_MULT")) * atr):
        return None

    return {
        "signal": sig,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "pattern": f"ท่าที่ 63 AllIn4S_DMxSP_FVG_{sig}",
        "reason": (
            f"DMxSP zone={zone_height/atr:.2f}ATR sweep={int(sweep_buy or sweep_sell)} "
            f"fvg={int(fvg)} bodyATR={body/atr:.2f}"
        ),
        "order_mode": "market",
        "signal_bar_time": int(cur["time"]),
        "atr_at_signal": atr,
    }


def detect_s63(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    if rates is None or len(rates) < 80:
        return {"signal": "WAIT", "reason": "S63: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S63: นอก session"}
    closed = rates[:-1]
    found = _detect_closed(closed, len(closed) - 1, cfg or S63_DEFAULTS)
    if found is None:
        return {"signal": "WAIT", "reason": "S63: ยังไม่ครบ DMxSP/FVG"}
    return found


def strategy_63(rates, tf: str = "", cfg: dict | None = None):
    return detect_s63(rates, tf=tf, dt_bkk=None, cfg=cfg)
