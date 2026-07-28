# -*- coding: utf-8 -*-
"""S191 - Upper EVT Hill-tail structural-sweep reclaim SELL, 16R."""

from __future__ import annotations

from strategy190 import DEFAULT_CFG as _S190_DEFAULT_CFG
from strategy190 import detect_s190


DEFAULT_CFG = dict(_S190_DEFAULT_CFG)
DEFAULT_CFG.update({"TP_RR": 16.00, "BE_RR": 1.00})


def detect_s191(rates, tf, dt_bkk, cfg):
    """Trade only the bearish half of S190's EVT structural-sweep anomaly."""
    merged = dict(DEFAULT_CFG)
    if cfg:
        merged.update(cfg)
    result = detect_s190(rates, tf, dt_bkk, merged)
    if result.get("signal") != "SELL":
        if result.get("signal") == "BUY":
            return {"signal": "WAIT", "reason": "S191 excludes lower-tail BUY asymmetry"}
        return result
    rr = max(7.0, float(merged["TP_RR"]))
    result = dict(result)
    result["pattern"] = f"S191 SELL Upper EVT Hill Sweep {rr:g}R"
    result["reason"] = f"Bearish-only EVT tail edge; {result['reason']}"
    return result
