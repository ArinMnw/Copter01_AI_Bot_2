# -*- coding: utf-8 -*-
"""S223 - Rollover opening drive on the session's first conviction bar, 10R.

Why this trigger and not another: testing S202's sweep-reclaim structure inside
the 04-06 rollover window produced *zero* signals in both validation windows,
even with its gates removed. The reason is structural — that pattern needs price
to exceed a 44-bar (~3.7h) extreme and reclaim it inside a 2-hour quiet session,
which essentially never happens. So the rollover window only admits *local*
triggers: S206 uses an 8-bar micro-range break, S221 a 3-bar run.

S223 takes the most local trigger available: the first conviction bar of the
session itself. It fires before a micro-range has even formed, betting that the
settlement flow S206 harvests is strongest right at the session open rather than
after a range has built. That makes it a different sample of the same edge
source, not a relabelled S206.
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
    # How many bars into the session still count as "the open".
    "OPEN_BARS": 3,
    "BODY_MIN_FRACTION": 0.60,
    "BODY_MIN_ATR": 0.25,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s223(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Take the first conviction bar after the rollover session opens."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        open_bars = max(1, int(c["OPEN_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < period + open_bars + 6 or dt_bkk is None:
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

    # Only act inside the first `open_bars` bars of today's session: count how
    # many bars before this one already belong to the same session and day.
    today = dt_bkk.date()
    elapsed = 0
    for bar in reversed(bars[:-1]):
        moment = datetime.fromtimestamp(int(bar["time"]), tz=BKK)
        if moment.date() != today or not start_hour <= moment.hour < end_hour:
            break
        elapsed += 1
        if elapsed >= open_bars:
            break
    if elapsed >= open_bars:
        return _wait(f"Past the session open ({elapsed} bars elapsed)")

    trigger = bars[-1]
    body = trigger["close"] - trigger["open"]
    bar_range = trigger["high"] - trigger["low"]
    if bar_range <= 0.0:
        return _wait("Trigger bar range is zero")
    if abs(body) < bar_range * float(c["BODY_MIN_FRACTION"]):
        return _wait("Opening bar lacks body conviction")
    if abs(body) < atr * float(c["BODY_MIN_ATR"]):
        return _wait("Opening bar body is too small versus ATR")
    side = 1 if body > 0.0 else -1

    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(trigger["close"], 2)
    if side > 0:
        sl = math.floor((trigger["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((trigger["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Open-drive risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Open-drive risk too large versus price")

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
        "pattern": f"S223 {signal} Rollover Open Drive {rr:g}R",
        "reason": (f"Conviction bar {elapsed + 1} of the rollover open "
                   f"(body {abs(body) / bar_range:.0%} of range)"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
