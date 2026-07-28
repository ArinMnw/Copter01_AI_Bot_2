# -*- coding: utf-8 -*-
"""S226 - Rollover opening-range SECOND break after a failed first, 10R.

The complement of S224. S224 trades only the day's *first* close beyond the
anchored opening range and explicitly discards any day where that range was
already broken. S226 takes exactly those discarded days: the first break failed
(price closed back inside the range), and then price breaks out again.

The mechanism is different from a plain breakout. A failed first break means the
initial move ran into supply/demand and was rejected; a second break after that
rejection has to clear participants who just faded the first one, so it carries
more information about genuine settlement flow. Same fresh session-formed anchor
as S224 (which S225 showed is the requirement — stale pre-session anchors fail),
same tight-range filter, same short stop on the break bar.
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
    # Bars of the session that define the anchored opening range.
    "OR_BARS": 6,
    "BREAK_BODY_MIN_FRACTION": 0.40,
    # Tight-range requirement — the classic ORB form (compression then
    # expansion). 2.0 is the value that clears both validation windows with the
    # best return/DD (12m +328.68, worst DD 19.78, ratio 16.6 vs 4.8 unfiltered).
    # Below ~1.5 the 6-bar range is essentially never that tight and n collapses.
    "OR_MAX_ATR": 2.0,          # 0 disables the filter
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _todays_session_bars(bars, day, start_hour, end_hour):
    """Bars of `day`'s session, oldest first (excludes nothing; caller slices)."""
    out = []
    for bar in bars:
        moment = datetime.fromtimestamp(int(bar["time"]), tz=BKK)
        if moment.date() == day and start_hour <= moment.hour < end_hour:
            out.append(bar)
    return out


def detect_s226(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a close beyond the rollover session's anchored opening range."""
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
    if rates is None or len(rates) < period + or_bars + 6 or dt_bkk is None:
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

    # Everything before the acting bar, from today's session only.
    prior = _todays_session_bars(bars[:-1], dt_bkk.date(), start_hour, end_hour)
    if len(prior) < or_bars:
        return _wait(f"Opening range not complete ({len(prior)}/{or_bars} bars)")
    opening = prior[:or_bars]
    or_high = max(bar["high"] for bar in opening)
    or_low = min(bar["low"] for bar in opening)
    or_size = or_high - or_low
    if or_size <= 0.0:
        return _wait("Opening range is degenerate")
    or_cap = float(c["OR_MAX_ATR"])
    if or_cap > 0.0 and or_size > atr * or_cap:
        return _wait("Opening range is too wide")

    # Require a failed first break: the range was broken once, and price then
    # closed back inside it. Those are precisely the days S224 discards.
    broke_once = False
    came_back = False
    for bar in prior[or_bars:]:
        if bar["close"] > or_high or bar["close"] < or_low:
            broke_once = True
            came_back = False
        elif broke_once:
            came_back = True
    if not broke_once:
        return _wait("Opening range has not been broken yet today")
    if not came_back:
        return _wait("First break has not failed back into the range")

    breakout = bars[-1]
    body = breakout["close"] - breakout["open"]
    if breakout["close"] > or_high and body > 0.0:
        side = 1
    elif breakout["close"] < or_low and body < 0.0:
        side = -1
    else:
        return _wait("No re-break of the opening range")
    bar_range = breakout["high"] - breakout["low"]
    if bar_range <= 0.0 or abs(body) < bar_range * float(
            c["BREAK_BODY_MIN_FRACTION"]):
        return _wait("Break bar lacks body conviction")

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
        return _wait(f"ORB risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("ORB risk too large versus price")

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
        "pattern": f"S226 {signal} Rollover ORB Re-Break {rr:g}R",
        "reason": (f"Re-break of the {or_size:.2f} opening range after a "
                   "failed first break in the rollover session"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
