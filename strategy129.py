# -*- coding: utf-8 -*-
"""S129 — High-Conviction Asia-to-London Inventory Carry."""

from __future__ import annotations

import strategy128


DEFAULT_CFG = {
    "S128_CFG": {
        "ASIA_MOVE_MIN_ATR": 1.50,
        "ASIA_EFFICIENCY_MIN": 0.12,
        "ASIA_DELTA_MIN": 0.05,
        "PULLBACK_MIN_FRACTION": 0.08,
        "PULLBACK_MAX_FRACTION": 0.70,
    }
}


def detect_s129(rates, tf, dt_bkk, cfg):
    """Apply high-conviction inventory thresholds to S128 chronology."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    source_cfg = dict(DEFAULT_CFG["S128_CFG"])
    source_cfg.update(c.get("S128_CFG") or {})
    result = strategy128.detect_s128(rates, tf, dt_bkk, source_cfg)
    if result.get("signal") not in ("BUY", "SELL"):
        return {"signal": "WAIT", "reason": f"S128 source: {result.get('reason', 'WAIT')}"}
    output = dict(result)
    output["pattern"] = f"S129 {result['signal']} HighConv Inventory"
    output["reason"] = f"High-conviction Asia inventory thresholds; {result['reason']}"
    return output
