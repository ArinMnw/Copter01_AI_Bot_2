# -*- coding: utf-8 -*-
"""S155 — SELL-only optimized skew-tail resumption contribution test."""

from __future__ import annotations

from strategy153 import DEFAULT_CFG as S153_DEFAULT_CFG
from strategy153 import detect_s153


DEFAULT_CFG = dict(S153_DEFAULT_CFG)


def detect_s155(rates, tf, dt_bkk, cfg):
    """Return only the SELL branch of optimized S153."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    result = detect_s153(rates, tf, dt_bkk, c)
    if result.get("signal") == "BUY":
        return {"signal": "WAIT", "reason": "S155 measures only SELL skew-tail contribution"}
    if result.get("signal") != "SELL":
        return result
    output = dict(result)
    output["pattern"] = "S155 SELL Skew Tail Resume 10R"
    output["reason"] = f"SELL-only contribution filter; {result.get('reason', '')}"
    return output
