# -*- coding: utf-8 -*-
"""S127 — S121 with Early 0.75R Breakeven."""

from __future__ import annotations

import strategy121


DEFAULT_CFG = {"BE_RR": 0.75, "S121_CFG": {}}


def detect_s127(rates, tf, dt_bkk, cfg):
    """Keep S121 unchanged except advance breakeven to 0.75R."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        be_rr = float(c["BE_RR"])
        if be_rr <= 0.0:
            return {"signal": "WAIT", "reason": "BE_RR must be positive"}
    except (KeyError, TypeError, ValueError, OverflowError):
        return {"signal": "WAIT", "reason": "Invalid S127 cfg"}
    result = strategy121.detect_s121(rates, tf, dt_bkk, dict(c.get("S121_CFG") or {}))
    if result.get("signal") != "SELL":
        return {"signal": "WAIT", "reason": f"S121 source: {result.get('reason', 'WAIT')}"}
    output = dict(result)
    output["pattern"] = "S127 SELL RV Exhaustion BE0.75"
    output["reason"] = f"S121 with early BE={be_rr:.2f}R; {result['reason']}"
    output["be_rr"] = be_rr
    return output
