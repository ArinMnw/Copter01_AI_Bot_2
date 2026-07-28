# -*- coding: utf-8 -*-
"""S227 - Rollover opening-range first-break failure fade, 10R.

S224 follows the first close beyond a freshly anchored rollover opening range.
S226 waits for that first break to fail, then follows a later second break.
S227 captures the remaining event itself: the first breakout closes back inside
the range.  That close traps breakout participants and supplies a short-stop
mean-reversion entry in the opposite direction.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from strategy119 import _atr, _bars
from strategy197 import _wait


BKK = timezone(timedelta(hours=7))

DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 4,
    "SESSION_END_HOUR": 6,
    "OR_BARS": 6,
    "OR_MAX_ATR": 2.0,
    "FAIL_BODY_MIN_FRACTION": 0.35,
    "REENTRY_DEPTH_FRACTION": 0.05,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _todays_session_bars(bars, day, start_hour, end_hour):
    out = []
    for bar in bars:
        moment = datetime.fromtimestamp(int(bar["time"]), tz=BKK)
        if moment.date() == day and start_hour <= moment.hour < end_hour:
            out.append(bar)
    return out


def detect_s227(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade the first rollover OR breakout when it closes back inside."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        or_bars = max(2, int(c["OR_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < period + or_bars + 7 or dt_bkk is None:
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

    prior = _todays_session_bars(
        bars[:-1], dt_bkk.date(), start_hour, end_hour
    )
    if len(prior) < or_bars + 1:
        return _wait("Opening range or first break not complete")
    opening = prior[:or_bars]
    or_high = max(bar["high"] for bar in opening)
    or_low = min(bar["low"] for bar in opening)
    or_size = or_high - or_low
    if or_size <= 0.0:
        return _wait("Opening range is degenerate")
    or_cap = float(c["OR_MAX_ATR"])
    if or_cap > 0.0 and or_size > atr * or_cap:
        return _wait("Opening range is too wide")

    # The immediately preceding bar must be the day's first close outside the
    # anchored range.  This prevents repeated signals after an earlier break.
    breakout = prior[-1]
    earlier = prior[or_bars:-1]
    if any(bar["close"] > or_high or bar["close"] < or_low for bar in earlier):
        return _wait("Opening range was already broken earlier today")
    if breakout["close"] > or_high:
        break_side = 1
    elif breakout["close"] < or_low:
        break_side = -1
    else:
        return _wait("Previous bar is not the first opening-range break")

    failure = bars[-1]
    body = failure["close"] - failure["open"]
    bar_range = failure["high"] - failure["low"]
    if bar_range <= 0.0 or abs(body) < (
            bar_range * float(c["FAIL_BODY_MIN_FRACTION"])):
        return _wait("Failure bar lacks body conviction")
    depth = or_size * float(c["REENTRY_DEPTH_FRACTION"])
    if break_side > 0:
        if body >= 0.0 or failure["close"] > or_high - depth:
            return _wait("Upper break has not failed back inside the range")
        side = -1
    else:
        if body <= 0.0 or failure["close"] < or_low + depth:
            return _wait("Lower break has not failed back inside the range")
        side = 1

    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(failure["close"], 2)
    if side > 0:
        sl = math.floor(
            (min(breakout["low"], failure["low"]) - buffer + 1e-12) * 100.0
        ) / 100.0
    else:
        sl = math.ceil(
            (max(breakout["high"], failure["high"]) + buffer - 1e-12) * 100.0
        ) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Failure-fade risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Failure-fade risk too large versus price")

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
        "pattern": f"S227 {signal} Rollover ORB Failure Fade {rr:g}R",
        "reason": (
            f"First break of the {or_size:.2f} opening range failed back inside"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
