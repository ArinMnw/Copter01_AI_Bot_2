# -*- coding: utf-8 -*-
"""S242 - Positive CLV-pressure downside sweep reclaim, 10R.

Unlike the failed counter-pressure S241, this continuation-pullback setup
requires persistent positive auction pressure before a temporary downside
sweep reclaims its range.  The wick supplies a structural short stop while the
long-side pressure aligns with S240's surviving direction.
"""

from __future__ import annotations

from strategy241 import DEFAULT_CFG as S241_DEFAULT_CFG
from strategy241 import detect_s241


DEFAULT_CFG = {
    **S241_DEFAULT_CFG,
    "PRESSURE_MODE": "positive",
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def detect_s242(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Buy a reclaimed pullback sweep inside persistent positive CLV pressure."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    signal = detect_s241(rates, tf, dt_bkk, c, **kwargs)
    if signal.get("signal") != "BUY":
        return signal
    rr = max(7.0, float(c["TP_RR"]))
    signal = dict(signal)
    signal["pattern"] = f"S242 BUY Positive-CLV Pullback Reclaim {rr:g}R"
    signal["reason"] = signal["reason"].replace(
        "negative CLV pressure",
        "positive CLV pressure",
    )
    return signal
