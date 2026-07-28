# -*- coding: utf-8 -*-
"""S187 - Bearish variance-ratio return-shock reclaim SELL, 8.1R."""

from __future__ import annotations

from strategy186 import DEFAULT_CFG as _S186_DEFAULT_CFG
from strategy186 import detect_s186


DEFAULT_CFG = dict(_S186_DEFAULT_CFG)
DEFAULT_CFG.update({"TP_RR": 8.10, "BE_RR": 0.76})


def detect_s187(rates, tf, dt_bkk, cfg):
    """Trade only the bearish half of S186's anti-persistent return shock."""
    merged = dict(DEFAULT_CFG)
    if cfg:
        merged.update(cfg)
    result = detect_s186(rates, tf, dt_bkk, merged)
    if result.get("signal") != "SELL":
        if result.get("signal") == "BUY":
            return {
                "signal": "WAIT",
                "reason": "S187 excludes bullish variance-ratio asymmetry",
            }
        return result
    rr = max(7.0, float(merged["TP_RR"]))
    result = dict(result)
    result["pattern"] = f"S187 SELL Bearish Variance-Ratio Reclaim {rr:g}R"
    result["reason"] = f"Bearish-only anti-persistent edge; {result['reason']}"
    return result
