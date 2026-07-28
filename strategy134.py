# -*- coding: utf-8 -*-
"""S134 — Asia Inventory Carry with a convex 7R payoff."""

from __future__ import annotations

from strategy128 import DEFAULT_CFG as S128_DEFAULT_CFG
from strategy128 import detect_s128


DEFAULT_CFG = {
    **S128_DEFAULT_CFG,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s134(rates, tf, dt_bkk, cfg):
    """Use S128's closed-bar carry setup with a 7R target and 1R BE."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        c["TP_RR"] = max(7.0, float(c["TP_RR"]))
        c["BE_RR"] = float(c["BE_RR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    result = detect_s128(rates, tf, dt_bkk, c)
    if result.get("signal") not in ("BUY", "SELL"):
        return result
    result = dict(result)
    risk = (result["entry"] - result["sl"] if result["signal"] == "BUY"
            else result["sl"] - result["entry"])
    realised_rr = (abs(result["tp"] - result["entry"]) / risk if risk > 0.0 else 0.0)
    result["pattern"] = f"S134 {result['signal']} Asia Carry 7R"
    result["reason"] = (f"{result.get('reason', '')}; convex target="
                        f"{realised_rr:.2f}R, BE={c['BE_RR']:.2f}R")
    return result
