# -*- coding: utf-8 -*-
"""S137 — S136 downside capitulation with no breakeven truncation."""

from __future__ import annotations

from strategy136 import detect_s136


DEFAULT_CFG = {"S136_CFG": {}}


def detect_s137(rates, tf, dt_bkk, cfg):
    """Keep the S136 7R geometry and disable breakeven management."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        source_cfg = dict(c.get("S136_CFG") or {})
    except (TypeError, ValueError, AttributeError) as exc:
        return {"signal": "WAIT", "reason": f"Invalid config: {exc}"}
    result = detect_s136(rates, tf, dt_bkk, source_cfg)
    if result.get("signal") != "BUY":
        return result
    output = dict(result)
    output["be_rr"] = None
    output["pattern"] = "S137 BUY Downside Capitulation 7R No-BE"
    output["reason"] = f"No-BE payoff experiment; {result.get('reason', '')}"
    return output
