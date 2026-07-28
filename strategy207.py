# -*- coding: utf-8 -*-
"""S207 - Rollover micro-range sweep failure reversal with a wick stop, 10R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 4,
    "SESSION_END_HOUR": 6,
    "RANGE_BARS": 8,
    "SWEEP_MIN_PIERCE_FRACTION": 0.10,
    "CLOSE_BACK_MIN_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s207(rates, tf, dt_bkk, cfg):
    """Fade a failed micro-range sweep during the rollover session."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        range_bars = max(4, int(c["RANGE_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = range_bars + period + 6
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside rollover session window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    micro_range = bars[-range_bars - 1:-1]
    range_high = max(bar["high"] for bar in micro_range)
    range_low = min(bar["low"] for bar in micro_range)
    range_size = range_high - range_low
    if range_size <= 0.0:
        return _wait("Micro range is degenerate")

    sweep = bars[-1]
    sweep_range = sweep["high"] - sweep["low"]
    if sweep_range <= 0.0:
        return _wait("Sweep bar range is zero")
    pierce_floor = range_size * float(c["SWEEP_MIN_PIERCE_FRACTION"])
    close_location = (sweep["close"] - sweep["low"]) / sweep_range
    edge = float(c["CLOSE_BACK_MIN_FRACTION"])
    if (sweep["low"] < range_low - pierce_floor
            and sweep["close"] > range_low
            and close_location >= edge):
        side = 1
    elif (sweep["high"] > range_high + pierce_floor
            and sweep["close"] < range_high
            and close_location <= 1.0 - edge):
        side = -1
    else:
        return _wait("No failed sweep of the micro range")

    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(sweep["close"], 2)
    if side > 0:
        sl = math.floor((sweep["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((sweep["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Sweep risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Sweep risk too large versus price")

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
        "pattern": f"S207 {signal} Rollover Sweep Fail {rr:g}R",
        "reason": (f"Failed sweep of {range_size:.2f} micro range at rollover; "
                   f"risk={risk:.2f}"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
