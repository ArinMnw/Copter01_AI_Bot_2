# -*- coding: utf-8 -*-
"""S239 - Signed-effort aligned range breakout, optimized 46.9R.

This controlled S238 ablation removes only the low-displacement absorption
requirement.  It tests whether persistent signed tick-volume effort itself
confirms an efficient range release during the US liquidity window.
"""

from __future__ import annotations

import math

from strategy238 import DEFAULT_CFG as S238_DEFAULT_CFG
from strategy238 import detect_s238


DEFAULT_CFG = {
    **S238_DEFAULT_CFG,
    "MAX_PRICE_DISPLACEMENT_ATR": math.inf,
    "TP_RR": 46.90,
    "BE_RR": 1.05,
}


def detect_s239(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a range break aligned with persistent signed tick-volume effort."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    signal = detect_s238(rates, tf, dt_bkk, c, **kwargs)
    if signal.get("signal") not in ("BUY", "SELL"):
        return signal
    side = signal["signal"]
    rr = max(7.0, float(c["TP_RR"]))
    signal = dict(signal)
    signal["pattern"] = f"S239 {side} Signed-Effort Aligned Break {rr:g}R"
    signal["reason"] = signal["reason"].replace(
        "release after absorbed signed effort",
        "range release aligned with persistent signed effort",
    )
    return signal
