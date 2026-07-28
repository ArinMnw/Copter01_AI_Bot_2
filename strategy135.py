# -*- coding: utf-8 -*-
"""S135 — Optimized upside-volatility exhaustion with a convex >=7R target."""

from __future__ import annotations

import math

from strategy121 import detect_s121


DEFAULT_CFG = {
    "SOURCE_CFG": {"S120_CFG": {
        "MAX_RISK_ATR": 2.50,
        "RV_EXPANSION_MIN": 2.00,
        "PREVIOUS_RV_MAX": 1.00,
    }},
    "TP_RR": 14.00,
    "BE_RR": 1.00,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s135(rates, tf, dt_bkk, cfg):
    """Keep S121 entries and stops, replacing only its payoff with >=7R."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        rr = max(7.0, float(c["TP_RR"]))
        be_rr = float(c["BE_RR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    result = detect_s121(rates, tf, dt_bkk, dict(c.get("SOURCE_CFG") or {}))
    if result.get("signal") != "SELL":
        return result
    output = dict(result)
    risk = float(output["sl"]) - float(output["entry"])
    if risk <= 0.0:
        return _wait("Invalid source risk")
    raw_tp = float(output["entry"]) - rr * risk
    output["tp"] = math.floor((raw_tp + 1e-12) * 100) / 100
    output["be_rr"] = be_rr
    output["pattern"] = f"S135 SELL Upside RV Exhaustion {rr:g}R"
    output["reason"] = f"{output.get('reason', '')}; target={rr:.2f}R, BE={be_rr:.2f}R"
    return output
