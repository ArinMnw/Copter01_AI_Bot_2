# -*- coding: utf-8 -*-
"""S240 - CLV-volume pressure aligned range breakout, optimized 42R.

Close Location Value measures auction pressure from where each bar closes
inside its high-low range.  Weighting CLV by tick volume captures persistent
buying or selling pressure without relying on candle-open direction.
"""

from __future__ import annotations

import math

from strategy238 import DEFAULT_CFG as S238_DEFAULT_CFG
from strategy238 import detect_s238


DEFAULT_CFG = {
    **S238_DEFAULT_CFG,
    "EFFORT_MODE": "clv",
    "MAX_PRICE_DISPLACEMENT_ATR": math.inf,
    "ALLOW_BUY": True,
    "ALLOW_SELL": False,
    "TP_RR": 42.00,
    "BE_RR": 0.08,
}


def detect_s240(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a range break aligned with volume-weighted CLV pressure."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    signal = detect_s238(rates, tf, dt_bkk, c, **kwargs)
    if signal.get("signal") not in ("BUY", "SELL"):
        return signal
    side = signal["signal"]
    if side == "BUY" and not bool(c["ALLOW_BUY"]):
        return {"signal": "WAIT", "reason": "BUY pressure branch is disabled"}
    if side == "SELL" and not bool(c["ALLOW_SELL"]):
        return {"signal": "WAIT", "reason": "SELL pressure branch failed survival"}
    rr = max(7.0, float(c["TP_RR"]))
    signal = dict(signal)
    signal["pattern"] = f"S240 {side} CLV-Volume Pressure Break {rr:g}R"
    signal["reason"] = signal["reason"].replace(
        "release after absorbed signed effort",
        "range release aligned with volume-weighted CLV pressure",
    )
    return signal
