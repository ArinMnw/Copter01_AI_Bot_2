# -*- coding: utf-8 -*-
"""S124 — Blended Reversal/Expansion Stop for S121."""

from __future__ import annotations

import math

import strategy121
from strategy119 import _atr, _bars


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "REVERSAL_BUFFER_ATR": 0.20,
    "EXPANSION_STOP_WEIGHT": 0.50,
    "TP_RR": 1.80,
    "MAX_RISK_ATR": 3.50,
    "S121_CFG": {},
}


def detect_s124(rates, tf, dt_bkk, cfg):
    """Blend S123's tight stop with the original S121 expansion stop."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    source = strategy121.detect_s121(rates, tf, dt_bkk, dict(c.get("S121_CFG") or {}))
    if source.get("signal") != "SELL":
        return {"signal": "WAIT", "reason": f"S121 source: {source.get('reason', 'WAIT')}"}
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], int(c["ATR_PERIOD"]))
        entry, expansion_sl = float(source["entry"]), float(source["sl"])
        reversal_sl = bars[-1]["high"] + atr * float(c["REVERSAL_BUFFER_ATR"])
        weight = float(c["EXPANSION_STOP_WEIGHT"])
        if not 0.0 <= weight <= 1.0:
            return {"signal": "WAIT", "reason": "Stop weight must be 0..1"}
        sl = reversal_sl + weight * (expansion_sl - reversal_sl)
        risk = sl - entry
        if atr <= 0.0 or risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
            return {"signal": "WAIT", "reason": "Blended risk is invalid"}
        rr = max(1.5, float(c["TP_RR"]))
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return {"signal": "WAIT", "reason": "Invalid S124 input or cfg"}
    entry, sl = round(entry, 2), round(sl, 2)
    risk = sl - entry
    if risk <= 0.0:
        return {"signal": "WAIT", "reason": "Risk vanished after rounding"}
    tp = math.floor((entry - rr * risk + 1e-12) * 100.0) / 100.0
    return {
        "signal": "SELL", "entry": entry, "sl": sl, "tp": tp,
        "order_type": "limit", "pattern": "S124 SELL Blended RV Stop",
        "reason": (f"S121 with {weight:.0%} expansion-stop weight, risk={risk / atr:.2f}ATR; "
                   f"{source['reason']}"),
        "be_rr": source.get("be_rr", 1.0),
        "cancel_bars": source.get("cancel_bars", 3),
    }
