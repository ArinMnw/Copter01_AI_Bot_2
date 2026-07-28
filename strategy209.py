# -*- coding: utf-8 -*-
"""S209 - Fresh daily-extreme breakout with a recent-swing stop, 10R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "CHANNEL_BARS": 288,
    "SWING_BARS": 4,
    "BREAK_MIN_ATR": 0.05,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s209(rates, tf, dt_bkk, cfg):
    """Trade a close beyond the rolling daily extreme with a tight swing stop."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        channel_bars = max(24, int(c["CHANNEL_BARS"]))
        swing_bars = max(2, int(c["SWING_BARS"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = channel_bars + period + 4
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    channel = bars[-channel_bars - 1:-1]
    channel_high = max(bar["high"] for bar in channel)
    channel_low = min(bar["low"] for bar in channel)
    breakout = bars[-1]
    margin = atr * float(c["BREAK_MIN_ATR"])
    if breakout["close"] > channel_high + margin:
        side = 1
    elif breakout["close"] < channel_low - margin:
        side = -1
    else:
        return _wait("Close is inside the rolling daily channel")

    swing = bars[-swing_bars - 1:-1] + [breakout]
    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(breakout["close"], 2)
    if side > 0:
        sl_raw = min(bar["low"] for bar in swing) - buffer
        sl = math.floor((sl_raw + 1e-12) * 100.0) / 100.0
    else:
        sl_raw = max(bar["high"] for bar in swing) + buffer
        sl = math.ceil((sl_raw - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Breakout risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Breakout risk too large versus price")

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
        "pattern": f"S209 {signal} Daily-Extreme Drive {rr:g}R",
        "reason": f"Close beyond rolling {channel_bars}-bar extreme; risk={risk:.2f}",
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
