# -*- coding: utf-8 -*-
"""S125 — S121 Upside Exhaustion without Breakeven Truncation."""

from __future__ import annotations

import strategy121


DEFAULT_CFG = {"S121_CFG": {}}


def detect_s125(rates, tf, dt_bkk, cfg):
    """Keep S121 geometry but let every filled trade resolve at SL or TP."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    result = strategy121.detect_s121(rates, tf, dt_bkk, dict(c.get("S121_CFG") or {}))
    if result.get("signal") != "SELL":
        return {"signal": "WAIT", "reason": f"S121 source: {result.get('reason', 'WAIT')}"}
    output = dict(result)
    output["pattern"] = "S125 SELL RV Exhaustion NoBE"
    output["reason"] = f"S121 geometry with BE disabled; {result['reason']}"
    output["be_rr"] = None
    return output
