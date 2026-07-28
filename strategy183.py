# -*- coding: utf-8 -*-
"""S183 - Upper range/close-variance liquidity-sweep reclaim SELL, 10.3R."""

from __future__ import annotations

from strategy181 import DEFAULT_CFG as _S181_DEFAULT_CFG
from strategy181 import detect_s181


DEFAULT_CFG = dict(_S181_DEFAULT_CFG)
DEFAULT_CFG.update({"TP_RR": 10.30, "BE_RR": 0.92})


def detect_s183(rates, tf, dt_bkk, cfg):
    """Trade only the bearish half of S181's range-variance sweep anomaly."""
    merged = dict(DEFAULT_CFG)
    if cfg:
        merged.update(cfg)
    result = detect_s181(rates, tf, dt_bkk, merged)
    if result.get("signal") != "SELL":
        if result.get("signal") == "BUY":
            return {
                "signal": "WAIT",
                "reason": "S183 excludes lower-sweep BUY asymmetry",
            }
        return result
    rr = max(7.0, float(merged["TP_RR"]))
    result = dict(result)
    result["pattern"] = f"S183 SELL Upper Range-Variance Sweep {rr:g}R"
    result["reason"] = f"Bearish-only range-variance edge; {result['reason']}"
    return result
