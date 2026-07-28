# -*- coding: utf-8 -*-
"""S126 — S121 with Delayed 1.25R Breakeven."""

from __future__ import annotations

import strategy121


DEFAULT_CFG = {"BE_RR": 1.25, "S121_CFG": {}}


def detect_s126(rates, tf, dt_bkk, cfg):
    """Keep S121 unchanged except delay breakeven from 1.0R to 1.25R."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        be_rr = float(c["BE_RR"])
        if be_rr <= 0.0:
            return {"signal": "WAIT", "reason": "BE_RR must be positive"}
    except (KeyError, TypeError, ValueError, OverflowError):
        return {"signal": "WAIT", "reason": "Invalid S126 cfg"}
    result = strategy121.detect_s121(rates, tf, dt_bkk, dict(c.get("S121_CFG") or {}))
    if result.get("signal") != "SELL":
        return {"signal": "WAIT", "reason": f"S121 source: {result.get('reason', 'WAIT')}"}
    output = dict(result)
    output["pattern"] = "S126 SELL RV Exhaustion BE1.25"
    output["reason"] = f"S121 with delayed BE={be_rr:.2f}R; {result['reason']}"
    output["be_rr"] = be_rr
    return output
