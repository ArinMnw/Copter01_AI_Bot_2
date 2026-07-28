# -*- coding: utf-8 -*-
"""S225 - Pre-rollover range breakout (anchored to the quiet zone before), 10R.

The campaign's working model is: rollover edge = clock x structural-break
confirmation, and BOTH are required (S212 dropped the clock and lost; S223
dropped the break confirmation in the same window and lost). Two forms of
structure already clear the bar:

    S206 - rolling 8-bar micro-range (slides with price)
    S224 - anchored opening range (the session's own first 6 bars)

S225 tries the remaining anchor: the **consolidation formed before the session
opens** (02:00-04:00 BKK). The story is different from S224 — instead of asking
"did price leave the zone the session itself just built", it asks "did the
settlement flow push price out of the quiet zone that was already sitting there
when the session opened". The tight-range filter is included from the start
because S224 showed it is the decisive lever (ratio 4.8 -> 16.6).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from strategy119 import _atr, _bars
from strategy197 import _wait


BKK = timezone(timedelta(hours=7))

DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    # Trading window (the rollover session).
    "SESSION_START_HOUR": 4,
    "SESSION_END_HOUR": 6,
    # Reference window (the quiet zone before it).
    "PRE_START_HOUR": 2,
    "PRE_END_HOUR": 4,
    "PRE_MIN_BARS": 8,
    "PRE_MAX_ATR": 4.0,
    "BREAK_BODY_MIN_FRACTION": 0.40,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _bars_in_window(bars, day, start_hour, end_hour):
    out = []
    for bar in bars:
        moment = datetime.fromtimestamp(int(bar["time"]), tz=BKK)
        if moment.date() == day and start_hour <= moment.hour < end_hour:
            out.append(bar)
    return out


def detect_s225(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade the first break of the pre-session zone once rollover opens."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
        pre_start = int(c["PRE_START_HOUR"])
        pre_end = int(c["PRE_END_HOUR"])
        pre_min_bars = max(2, int(c["PRE_MIN_BARS"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < period + pre_min_bars + 8 or dt_bkk is None:
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

    today = dt_bkk.date()
    pre = _bars_in_window(bars[:-1], today, pre_start, pre_end)
    if len(pre) < pre_min_bars:
        return _wait(f"Pre-session zone incomplete ({len(pre)} bars)")
    zone_high = max(bar["high"] for bar in pre)
    zone_low = min(bar["low"] for bar in pre)
    zone_size = zone_high - zone_low
    if zone_size <= 0.0:
        return _wait("Pre-session zone is degenerate")
    zone_cap = float(c["PRE_MAX_ATR"])
    if zone_cap > 0.0 and zone_size > atr * zone_cap:
        return _wait(f"Pre-session zone too wide ({zone_size / atr:.2f} ATR)")

    # Only the day's first break counts.
    for bar in _bars_in_window(bars[:-1], today, start_hour, end_hour):
        if bar["close"] > zone_high or bar["close"] < zone_low:
            return _wait("Pre-session zone was already broken today")

    breakout = bars[-1]
    body = breakout["close"] - breakout["open"]
    if breakout["close"] > zone_high and body > 0.0:
        side = 1
    elif breakout["close"] < zone_low and body < 0.0:
        side = -1
    else:
        return _wait("No fresh close beyond the pre-session zone")
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
        return _wait(f"Break risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Break risk too large versus price")

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
        "pattern": f"S225 {signal} Pre-Rollover Zone Break {rr:g}R",
        "reason": (f"First rollover close beyond the {zone_size / atr:.2f}-ATR "
                   f"pre-session zone ({pre_start:02d}-{pre_end:02d} BKK)"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
