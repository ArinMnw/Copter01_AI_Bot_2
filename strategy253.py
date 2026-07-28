# -*- coding: utf-8 -*-
"""S253 - BUY-only ATR directional-change reversal, 10R."""

from __future__ import annotations

from strategy252 import DEFAULT_CFG as S252_DEFAULT_CFG
from strategy252 import detect_s252


DEFAULT_CFG = {
    **S252_DEFAULT_CFG,
    "ALLOW_BUY": True,
    "ALLOW_SELL": False,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def detect_s253(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade only upside ATR directional-change reversal events."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    signal = detect_s252(rates, tf, dt_bkk, c, **kwargs)
    if signal.get("signal") != "BUY":
        return signal
    rr = max(7.0, float(c["TP_RR"]))
    signal = dict(signal)
    signal["pattern"] = f"S253 BUY ATR Directional-Change Reversal {rr:g}R"
    return signal
