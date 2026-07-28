# -*- coding: utf-8 -*-
"""S122 — Upside RV Exhaustion with Signed-Volume Deceleration."""

from __future__ import annotations

import strategy121
from strategy116 import _normalise_rates, _normalised_delta


DEFAULT_CFG = {
    "DELTA_WINDOW": 4,
    "DELTA_DECELERATION_MIN": 0.05,
    "S121_CFG": {},
}


def detect_s122(rates, tf, dt_bkk, cfg):
    """Confirm S121 only when late signed volume weakens versus early impulse."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        window = int(c["DELTA_WINDOW"])
        minimum = float(c["DELTA_DECELERATION_MIN"])
        if window < 2 or minimum < 0.0:
            return {"signal": "WAIT", "reason": "Invalid S122 cfg"}
    except (KeyError, TypeError, ValueError, OverflowError):
        return {"signal": "WAIT", "reason": "Invalid S122 cfg"}
    if rates is None or len(rates) < window * 2:
        return {"signal": "WAIT", "reason": "Not enough data"}
    source_cfg = dict(c.get("S121_CFG") or {})
    result = strategy121.detect_s121(rates, tf, dt_bkk, source_cfg)
    if result.get("signal") != "SELL":
        return {"signal": "WAIT", "reason": f"S121 source: {result.get('reason', 'WAIT')}"}
    try:
        bars = _normalise_rates(rates)
        early = _normalised_delta(bars[-2 * window:-window])
        late = _normalised_delta(bars[-window:])
    except (KeyError, TypeError, ValueError, OverflowError):
        return {"signal": "WAIT", "reason": "Invalid rates"}
    deceleration = early - late
    if deceleration < minimum:
        return {"signal": "WAIT", "reason": f"Buy delta did not decelerate ({deceleration:+.2f})"}
    output = dict(result)
    output["pattern"] = "S122 SELL RV Delta Deceleration"
    output["reason"] = (
        f"Signed-volume delta decelerated {early:+.2f}->{late:+.2f}; "
        f"{result['reason']}"
    )
    return output
