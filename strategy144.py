# -*- coding: utf-8 -*-
"""S144 — London-to-New-York directional inventory carry transfer."""

from __future__ import annotations

from strategy128 import DEFAULT_CFG as S128_DEFAULT_CFG
from strategy128 import detect_s128


DEFAULT_CFG = {
    **S128_DEFAULT_CFG,
    "ASIA_START_HOUR": 14,
    "ASIA_END_HOUR": 19,
    "LONDON_HOURS": (19, 20, 21),
    "ASIA_MIN_BARS": 48,
    "TP_RR": 1.80,
    "BE_RR": 1.00,
}


def detect_s144(rates, tf, dt_bkk, cfg):
    """Apply S128 inventory chronology to the London-to-NY handoff."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    result = detect_s128(rates, tf, dt_bkk, c)
    if result.get("signal") not in ("BUY", "SELL"):
        return result
    output = dict(result)
    output["pattern"] = f"S144 {result['signal']} London-NY Inventory Carry"
    output["reason"] = f"London-to-NY session transfer; {result.get('reason', '')}"
    return output
