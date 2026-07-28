# -*- coding: utf-8 -*-
"""S136 — Downside-volatility capitulation reclaim with a short 7R stop.

S135 monetises upside-exhaustion SELL tails.  S136 tests the complementary
event: a first, inefficient downside volatility expansion followed by a
closed bullish reversal.  It retains S120's chronology but replaces the wide
expansion-window stop with a reversal-candle structural stop and requires a
convex target of at least 7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy120 import detect_s120


DEFAULT_CFG = {
    "SOURCE_CFG": {
        "RV_EXPANSION_MIN": 2.00,
        "PREVIOUS_RV_MAX": 1.00,
        "MAX_RISK_ATR": 2.50,
    },
    "ATR_PERIOD": 14,
    "SL_REVERSAL_BUFFER_ATR": 0.15,
    "MAX_SHORT_RISK_ATR": 1.25,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s136(rates, tf, dt_bkk, cfg):
    """Detect a closed-bar downside capitulation and return a BUY limit."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        buffer_atr = max(0.0, float(c["SL_REVERSAL_BUFFER_ATR"]))
        max_risk_atr = float(c["MAX_SHORT_RISK_ATR"])
        rr = max(7.0, float(c["TP_RR"]))
        be_rr = float(c["BE_RR"])
        source_cfg = dict(c.get("SOURCE_CFG") or {})
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")

    result = detect_s120(rates, tf, dt_bkk, source_cfg)
    if result.get("signal") == "SELL":
        return _wait("S136 accepts only downside-capitulation BUY events")
    if result.get("signal") != "BUY":
        return _wait(f"S120 source: {result.get('reason', 'WAIT')}")
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
        ratio = risk / atr if atr else math.inf
        return _wait(f"Short structural risk outside range ({ratio:.2f} ATR)")
    raw_tp = entry + rr * risk
    tp = math.ceil((raw_tp - 1e-12) * 100) / 100
    output = dict(result)
    output.update({
        "signal": "BUY",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S136 BUY Downside Capitulation {rr:g}R",
        "reason": (f"Complementary downside RV capitulation; {result.get('reason', '')}; "
                   f"short risk={risk / atr:.2f}ATR, target={rr:.2f}R"),
        "be_rr": be_rr,
    })
    return output
