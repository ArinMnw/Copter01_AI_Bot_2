# -*- coding: utf-8 -*-
"""S143 — Bullish Asia-to-London inventory carry BUY diversifier."""

from __future__ import annotations

from strategy128 import DEFAULT_CFG as S128_DEFAULT_CFG
from strategy128 import detect_s128


DEFAULT_CFG = {**S128_DEFAULT_CFG, "TP_RR": 1.80, "BE_RR": 1.00}


def detect_s143(rates, tf, dt_bkk, cfg):
    """Return only the bullish branch of the proven S128 session carry."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    result = detect_s128(rates, tf, dt_bkk, c)
    if result.get("signal") == "SELL":
        return {"signal": "WAIT", "reason": "S143 is a BUY-only portfolio diversifier"}
    if result.get("signal") != "BUY":
        return result
    output = dict(result)
    output["pattern"] = "S143 BUY Bullish Asia Inventory Carry"
    output["reason"] = f"BUY-only diversification filter; {result.get('reason', '')}"
    return output
