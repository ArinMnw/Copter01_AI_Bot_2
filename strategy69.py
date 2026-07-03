"""
strategy69.py - S69 All-in-4S S63 Champion Filter Stack, RESEARCH/BACKTEST-ONLY

Standalone only: not imported by scanner.py/trailing.py/main.py.

Idea:
- keep S63 DMxSP breakout/reclaim as the entry engine
- add proven PDF-derived filters:
  - base FVG ladder context from S66
  - optional clear-candle confirmation from S67
"""

from strategy63 import S63_DEFAULTS, _detect_closed as _s63_detect_closed, _in_session


S69_DEFAULTS = dict(S63_DEFAULTS)
S69_DEFAULTS.update({
    "ENTRY_TF": "M5",
    "SP_LOOKBACK": 8,
    "SP_MAX_ATR": 1.4,
    "MODE": "breakout",
    "FVG_REQUIRED": False,
    "MIN_BODY_ATR": 0.35,
    "MIN_BODY_RATIO": 0.40,
    "TP_RR": 1.20,
    "SL_ATR_MULT": 0.35,
    "BASE_FVG_FILTER": True,
    "BASE_FVG_LOOKBACK": 80,
    "BASE_FVG_MIN_ATR": 0.04,
    "BASE_FVG_TOUCH_TOL_ATR": 0.25,
    "CLEAR_FILTER": False,
    "CLEAR_WICK_BODY_MULT": 0.6,
    "CLEAR_CLOSE": "body",
})


def _cfg(cfg, key):
    if cfg and key in cfg:
        return cfg[key]
    return S69_DEFAULTS[key]


def _bull(b):
    return float(b["close"]) > float(b["open"])


def _bear(b):
    return float(b["close"]) < float(b["open"])


def _body(b):
    return abs(float(b["close"]) - float(b["open"]))


def _upper_wick(b):
    return float(b["high"]) - max(float(b["open"]), float(b["close"]))


def _lower_wick(b):
    return min(float(b["open"]), float(b["close"])) - float(b["low"])


def _base_fvg_ok(closed, j, sig, atr, cfg):
    if not _cfg(cfg, "BASE_FVG_FILTER"):
        return True
    start = max(2, j - int(_cfg(cfg, "BASE_FVG_LOOKBACK")))
    min_gap = float(_cfg(cfg, "BASE_FVG_MIN_ATR")) * atr
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
    tol = float(_cfg(cfg, "BASE_FVG_TOUCH_TOL_ATR")) * atr
    cur = closed[j]
    return float(cur["low"]) <= zone["high"] + tol and float(cur["high"]) >= zone["low"] - tol


def _clear_ok(closed, j, sig, cfg):
    if not _cfg(cfg, "CLEAR_FILTER"):
        return True
    cur = closed[j]
    prev = closed[j - 1]
    body = max(_body(cur), 0.0001)
    if sig == "BUY":
        ok = _bull(cur) and _lower_wick(cur) >= float(_cfg(cfg, "CLEAR_WICK_BODY_MULT")) * body
        if _cfg(cfg, "CLEAR_CLOSE") == "wick":
            return ok and float(cur["close"]) > float(prev["high"])
        return ok and float(cur["close"]) > max(float(prev["open"]), float(prev["close"]))
    ok = _bear(cur) and _upper_wick(cur) >= float(_cfg(cfg, "CLEAR_WICK_BODY_MULT")) * body
    if _cfg(cfg, "CLEAR_CLOSE") == "wick":
        return ok and float(cur["close"]) < float(prev["low"])
    return ok and float(cur["close"]) < min(float(prev["open"]), float(prev["close"]))


def _detect_closed(closed, j, cfg, atr_value=None):
    sig = _s63_detect_closed(closed, j, cfg, atr_value=atr_value)
    if sig is None:
        return None
    atr = sig.get("atr_at_signal") or atr_value
    if not atr:
        return None
    direction = sig["signal"]
    if not _base_fvg_ok(closed, j, direction, atr, cfg):
        return None
    if not _clear_ok(closed, j, direction, cfg):
        return None
    sig = dict(sig)
    sig["pattern"] = f"ท่าที่ 69 AllIn4S_S63_FilterStack_{direction}"
    sig["reason"] = sig["reason"] + (
        f" | S69 baseFVG={int(_cfg(cfg, 'BASE_FVG_FILTER'))} clear={int(_cfg(cfg, 'CLEAR_FILTER'))}"
    )
    return sig


def detect_s69(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    cfg = cfg or S69_DEFAULTS
    if rates is None or len(rates) < 100:
        return {"signal": "WAIT", "reason": "S69: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S69: นอก session"}
    closed = rates[:-1]
    found = _detect_closed(closed, len(closed) - 1, cfg)
    if found is None:
        return {"signal": "WAIT", "reason": "S69: S63 ยังไม่ผ่าน filter stack"}
    return found


def strategy_69(rates, tf: str = "", cfg: dict | None = None):
    return detect_s69(rates, tf=tf, dt_bkk=None, cfg=cfg)
