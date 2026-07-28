# -*- coding: utf-8 -*-
"""S271 - BUY-only stationary OU residual continuation, optimized 21.3R."""

from __future__ import annotations

from strategy270 import DEFAULT_CFG as S270_DEFAULT_CFG
from strategy270 import detect_s270


DEFAULT_CFG = {
    **S270_DEFAULT_CFG,
    "ALLOW_BUY": True,
    "ALLOW_SELL": False,
    "TP_RR": 21.30,
    "BE_RR": 0.10,
}


def detect_s271(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Run the BUY branch of S270 after direction-survival evidence."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    signal = detect_s270(rates, tf, dt_bkk, c, **kwargs)
    if signal.get("signal") == "BUY":
        signal["pattern"] = signal["pattern"].replace("S270", "S271", 1)
        signal["reason"] = "BUY-only survival branch; " + signal["reason"]
    return signal
