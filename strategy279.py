# -*- coding: utf-8 -*-
"""S279 - BUY-only directional Ulcer-asymmetry breakout, 10R."""

from __future__ import annotations

from strategy278 import DEFAULT_CFG as S278_DEFAULT_CFG
from strategy278 import detect_s278


DEFAULT_CFG = {
    **S278_DEFAULT_CFG,
    "ALLOW_BUY": True,
    "ALLOW_SELL": False,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def detect_s279(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Run the BUY branch of S278 after direction attribution."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    signal = detect_s278(rates, tf, dt_bkk, c, **kwargs)
    if signal.get("signal") == "BUY":
        signal["pattern"] = signal["pattern"].replace("S278", "S279", 1)
        signal["reason"] = "BUY-only survival branch; " + signal["reason"]
    return signal
