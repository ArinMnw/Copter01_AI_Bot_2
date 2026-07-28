# -*- coding: utf-8 -*-
"""S251 - BUY-only CUSUM return-change-point breakout, 10R."""

from __future__ import annotations

from strategy250 import DEFAULT_CFG as S250_DEFAULT_CFG
from strategy250 import detect_s250


DEFAULT_CFG = {
    **S250_DEFAULT_CFG,
    "ALLOW_BUY": True,
    "ALLOW_SELL": False,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def detect_s251(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade only upside CUSUM change points with structural confirmation."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    signal = detect_s250(rates, tf, dt_bkk, c, **kwargs)
    if signal.get("signal") != "BUY":
        return signal
    rr = max(7.0, float(c["TP_RR"]))
    signal = dict(signal)
    signal["pattern"] = f"S251 BUY CUSUM Change-Point Break {rr:g}R"
    return signal
