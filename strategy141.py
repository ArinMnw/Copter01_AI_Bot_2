# -*- coding: utf-8 -*-
"""S141 — Coherent upside RV continuation BUY with a short 7R stop."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars, detect_s119


DEFAULT_CFG = {
    "SOURCE_CFG": {
        "RV_EXPANSION_MIN": 1.45,
        "PREVIOUS_RV_MAX": 1.00,
        "EFFICIENCY_MIN": 0.80,
    },
    "ATR_PERIOD": 14,
    "SL_SIGNAL_BUFFER_ATR": 0.15,
    "MAX_SHORT_RISK_ATR": 1.25,
    "MAX_RISK_PRICE_PCT": 0.40,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s141(rates, tf, dt_bkk, cfg):
    """Keep only coherent S119 upside expansion and apply short convex risk."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        buffer_atr = max(0.0, float(c["SL_SIGNAL_BUFFER_ATR"]))
        max_risk_atr = float(c["MAX_SHORT_RISK_ATR"])
        max_risk_pct = float(c["MAX_RISK_PRICE_PCT"])
        rr = max(7.0, float(c["TP_RR"]))
        source_cfg = dict(c.get("SOURCE_CFG") or {})
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid config: {exc}")
    result = detect_s119(rates, tf, dt_bkk, source_cfg)
    if result.get("signal") == "SELL":
        return _wait("S141 accepts only coherent upside-volatility continuation")
    if result.get("signal") != "BUY":
        return _wait(f"S119 source: {result.get('reason', 'WAIT')}")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        latest = bars[-1]
        entry = round(float(result["entry"]), 2)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid source data: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    sl = math.floor((latest["low"] - atr * buffer_atr + 1e-12) * 100) / 100
    risk = entry - sl
    if risk <= 0.0 or risk > atr * max_risk_atr:
        return _wait(f"Short signal-bar risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > max_risk_pct:
        return _wait(f"Short signal-bar risk too large versus price ({risk_pct:.2f}%)")
    tp = math.ceil((entry + rr * risk - 1e-12) * 100) / 100
    output = dict(result)
    output.update({
        "sl": sl, "tp": tp,
        "pattern": f"S141 BUY Upside RV Continuation {rr:g}R",
        "reason": (f"Coherent upside clustering; {result.get('reason', '')}; "
                   f"short risk={risk / atr:.2f}ATR/{risk_pct:.2f}%, target={rr:.2f}R"),
        "be_rr": float(c["BE_RR"]),
    })
    return output
