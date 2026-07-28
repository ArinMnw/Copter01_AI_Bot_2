# -*- coding: utf-8 -*-
"""S154 — BUY-only optimized skew-tail resumption portfolio diversifier."""

from __future__ import annotations

from strategy153 import DEFAULT_CFG as S153_DEFAULT_CFG
from strategy153 import detect_s153


DEFAULT_CFG = dict(S153_DEFAULT_CFG)


def detect_s154(rates, tf, dt_bkk, cfg):
    """Return only the BUY branch of optimized S153."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    result = detect_s153(rates, tf, dt_bkk, c)
    if result.get("signal") == "SELL":
        return {"signal": "WAIT", "reason": "S154 is a BUY-only directional diversifier"}
    if result.get("signal") != "BUY":
        return result
    output = dict(result)
    output["pattern"] = "S154 BUY Skew Tail Resume 10R"
    output["reason"] = f"BUY-only portfolio filter; {result.get('reason', '')}"
    return output
