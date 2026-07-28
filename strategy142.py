# -*- coding: utf-8 -*-
"""S142 — S141 coherent upside continuation with an attainable 2R target."""

from __future__ import annotations

import math

from strategy141 import detect_s141


DEFAULT_CFG = {"S141_CFG": {}, "TP_RR": 2.00, "BE_RR": 1.00}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s142(rates, tf, dt_bkk, cfg):
    """Keep S141 signal geometry and replace only its 7R target with 2R."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        rr = max(1.5, float(c["TP_RR"]))
        be_rr = float(c["BE_RR"])
        source_cfg = dict(c.get("S141_CFG") or {})
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid config: {exc}")
    result = detect_s141(rates, tf, dt_bkk, source_cfg)
    if result.get("signal") != "BUY":
        return result
    output = dict(result)
    entry, sl = float(output["entry"]), float(output["sl"])
    risk = entry - sl
    if risk <= 0.0:
        return _wait("Invalid source risk")
    output["tp"] = math.ceil((entry + rr * risk - 1e-12) * 100) / 100
    output["be_rr"] = be_rr
    output["pattern"] = f"S142 BUY Upside RV Continuation {rr:g}R"
    output["reason"] = f"Attainable-payoff test; {result.get('reason', '')}; target={rr:.2f}R"
    return output
