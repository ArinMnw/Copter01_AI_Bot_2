# -*- coding: utf-8 -*-
"""S206 - Rollover opening-drive breakout with a breakout-bar stop, 10R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 4,
    "SESSION_END_HOUR": 6,
    "SESSION_WEEKDAY": -1,
    "RANGE_BARS": 8,
    "BREAK_BODY_MIN_FRACTION": 0.40,
    "BREAK_VOLUME_MIN_RATIO": 0.0,
    "RANGE_MAX_ATR": 0.0,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s206(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade the first directional drive out of the pre-rollover micro-range."""
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
    weekday_filter = int(c.get("SESSION_WEEKDAY", -1))
    if weekday_filter >= 0 and dt_bkk.weekday() != weekday_filter:
        return _wait("Outside configured rollover weekday")
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

    breakout = bars[-1]
    body = breakout["close"] - breakout["open"]
    if breakout["close"] > range_high and body > 0.0:
        side = 1
    elif breakout["close"] < range_low and body < 0.0:
        side = -1
    else:
        return _wait("No directional drive out of the micro range")
    if abs(body) < range_size * float(c["BREAK_BODY_MIN_FRACTION"]):
        return _wait("Drive body is too small versus the micro range")
    range_cap = float(c["RANGE_MAX_ATR"])
    if range_cap > 0.0 and range_size > atr * range_cap:
        return _wait("Micro range is not compressed enough")
    volume_ratio_floor = float(c["BREAK_VOLUME_MIN_RATIO"])
    if volume_ratio_floor > 0.0:
        mean_volume = sum(bar["tick_volume"] for bar in micro_range) / len(micro_range)
        if mean_volume <= 0.0 or breakout["tick_volume"] < mean_volume * volume_ratio_floor:
            return _wait("Drive lacks volume expansion")

    buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        entry = breakout["close"]
        sl = math.floor((breakout["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        entry = breakout["close"]
        sl = math.ceil((breakout["high"] + buffer - 1e-12) * 100.0) / 100.0
    entry = round(entry, 2)
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Drive risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Drive risk too large versus price")

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
        "pattern": f"S206 {signal} Rollover Drive {rr:g}R",
        "reason": (f"Drive out of {range_size:.2f} micro range at rollover; "
                   f"risk={risk:.2f}"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
