# -*- coding: utf-8 -*-
"""S211 - Multi-bar climax fade at the rolling daily extreme, 10R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "CHANNEL_BARS": 288,
    "CLIMAX_BARS": 6,
    "CLIMAX_MIN_ATR": 3.00,
    "REVERSAL_BODY_MIN_ATR": 0.30,
    "SL_BARS": 2,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s211(rates, tf, dt_bkk, cfg):
    """Fade a multi-bar climax that just stretched beyond the daily extreme."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        channel_bars = max(24, int(c["CHANNEL_BARS"]))
        climax_bars = max(2, int(c["CLIMAX_BARS"]))
        sl_bars = max(1, int(c["SL_BARS"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = channel_bars + climax_bars + period + 4
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    reversal = bars[-1]
    climax = bars[-climax_bars - 1:-1]
    channel = bars[-channel_bars - climax_bars - 1:-climax_bars - 1]
    channel_high = max(bar["high"] for bar in channel)
    channel_low = min(bar["low"] for bar in channel)
    climax_move = climax[-1]["close"] - climax[0]["open"]
    if abs(climax_move) < atr * float(c["CLIMAX_MIN_ATR"]):
        return _wait("No multi-bar climax move")
    climax_high = max(bar["high"] for bar in climax)
    climax_low = min(bar["low"] for bar in climax)
    body = reversal["close"] - reversal["open"]
    if climax_move < 0.0 and climax_low < channel_low:
        side = 1
        if body < atr * float(c["REVERSAL_BODY_MIN_ATR"]):
            return _wait("No bullish reversal bar after the down climax")
    elif climax_move > 0.0 and climax_high > channel_high:
        side = -1
        if -body < atr * float(c["REVERSAL_BODY_MIN_ATR"]):
            return _wait("No bearish reversal bar after the up climax")
    else:
        return _wait("Climax did not stretch beyond the daily extreme")

    recent = bars[-sl_bars - 1:]
    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(reversal["close"], 2)
    if side > 0:
        sl = math.floor((min(bar["low"] for bar in recent) - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((max(bar["high"] for bar in recent) + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Climax risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Climax risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    if side > 0:
        signal = "BUY"
        tp = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
    else:
        signal = "SELL"
        tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S211 {signal} Climax Fade {rr:g}R",
        "reason": (f"{abs(climax_move) / atr:.1f}-ATR climax beyond daily extreme "
                   "with reversal bar"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
