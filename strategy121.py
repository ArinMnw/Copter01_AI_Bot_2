# -*- coding: utf-8 -*-
"""S121 — Asymmetric Upside-Volatility Exhaustion.

S120's two-month decomposition showed opposite behavior by shock direction.
S121 tests a market-microstructure hypothesis rather than an hour filter:
downside volatility clusters and is not faded, while inefficient upside
expansion may represent short-covering/exhaustion and is eligible for SELL.
"""

from __future__ import annotations

import strategy120


DEFAULT_CFG = {"S120_CFG": {}}


def detect_s121(rates, tf, dt_bkk, cfg):
    """Return only the upside-exhaustion SELL branch of S120."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    source_cfg = dict(c.get("S120_CFG") or {})
    result = strategy120.detect_s120(rates, tf, dt_bkk, source_cfg)
    if result.get("signal") == "BUY":
        return {"signal": "WAIT", "reason": "S121 does not fade downside volatility"}
    if result.get("signal") != "SELL":
        return {"signal": "WAIT", "reason": f"S120 source: {result.get('reason', 'WAIT')}"}
    output = dict(result)
    output["pattern"] = "S121 SELL Upside RV Exhaustion"
    output["reason"] = f"Asymmetric upside-only filter; {result['reason']}"
    return output
