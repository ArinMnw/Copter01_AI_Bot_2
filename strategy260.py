# -*- coding: utf-8 -*-
"""S260 - Bipower jump rejection continuation complement, 10R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy259 import DEFAULT_CFG as S259_DEFAULT_CFG
from strategy259 import detect_s259


DEFAULT_CFG = {
    **S259_DEFAULT_CFG,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def detect_s260(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow the jump whose exhaustion fade trigger failed in S259."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    fade = detect_s259(rates, tf, dt_bkk, c, **kwargs)
    if fade.get("signal") not in ("BUY", "SELL"):
        return fade
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], max(1, int(c["ATR_PERIOD"])))
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    event = bars[-1]
    entry = round(event["close"], 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    if fade["signal"] == "SELL":
        signal, side = "BUY", 1
        sl = math.floor((event["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        signal, side = "SELL", -1
        sl = math.ceil((event["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Continuation risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Continuation risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Continuation risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    if side > 0:
        tp = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
    else:
        tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S260 {signal} Bipower Jump Continuation {rr:g}R",
        "reason": (
            f"Follow jump after S259 fade trigger; "
            f"opposite={fade['signal']}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
