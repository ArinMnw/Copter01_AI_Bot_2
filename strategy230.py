# -*- coding: utf-8 -*-
"""S230 - Rollover micro-break aligned with opening-auction bias, 10R.

S206's rolling micro-range drive is profitable over six months but failed in the
latest two-month regime.  S230 asks the session's first six bars to establish a
directional auction bias, then accepts a later rolling-range break only when it
agrees with that bias and remains in the corresponding half of the anchored
opening range.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy228 import _todays_session_bars


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 4,
    "SESSION_END_HOUR": 6,
    "OR_BARS": 6,
    "OR_MAX_ATR": 2.5,
    "OPEN_BIAS_MIN_FRACTION": 0.15,
    "RANGE_BARS": 8,
    "BREAK_BODY_MIN_FRACTION": 0.40,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s230(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a rollover micro-break only with the opening auction's bias."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        or_bars = max(2, int(c["OR_BARS"]))
        range_bars = max(4, int(c["RANGE_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(period + range_bars + 6, period + or_bars + 6)
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

    prior_session = _todays_session_bars(
        bars[:-1], dt_bkk.date(), start_hour, end_hour
    )
    if len(prior_session) < or_bars:
        return _wait("Opening auction is not complete")
    opening = prior_session[:or_bars]
    or_high = max(bar["high"] for bar in opening)
    or_low = min(bar["low"] for bar in opening)
    or_size = or_high - or_low
    if or_size <= 0.0:
        return _wait("Opening range is degenerate")
    or_cap = float(c["OR_MAX_ATR"])
    if or_cap > 0.0 and or_size > atr * or_cap:
        return _wait("Opening auction range is too wide")
    opening_move = opening[-1]["close"] - opening[0]["open"]
    if abs(opening_move) < or_size * float(c["OPEN_BIAS_MIN_FRACTION"]):
        return _wait("Opening auction lacks directional bias")
    opening_side = 1 if opening_move > 0.0 else -1
    midpoint = (or_high + or_low) * 0.50

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
    if side != opening_side:
        return _wait("Micro break disagrees with opening-auction bias")
    if side > 0 and breakout["close"] <= midpoint:
        return _wait("Bullish break remains in lower opening-range half")
    if side < 0 and breakout["close"] >= midpoint:
        return _wait("Bearish break remains in upper opening-range half")
    if abs(body) < range_size * float(c["BREAK_BODY_MIN_FRACTION"]):
        return _wait("Drive body is too small versus the micro range")

    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(breakout["close"], 2)
    if side > 0:
        sl = math.floor((breakout["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((breakout["high"] + buffer - 1e-12) * 100.0) / 100.0
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
        "pattern": f"S230 {signal} Opening-Bias Micro Break {rr:g}R",
        "reason": (
            f"Micro-range drive aligned with {opening_move:.2f} opening-auction "
            f"move; OR={or_size:.2f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
