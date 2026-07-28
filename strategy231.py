# -*- coding: utf-8 -*-
"""S231 - First Asian rejection of each rollover-range edge, 10R.

S216 repeatedly fades the same 04:00-07:00 range edge throughout the Asian
morning.  Once an edge has already been tested, later rejections are no longer
independent liquidity events.  S231 accepts only the first touch/rejection of
that specific edge each day, preserving the mechanism while removing repeated
entries at a consumed level.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from strategy119 import _atr, _bars
from strategy197 import _wait


BKK = timezone(timedelta(hours=7))

DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 7,
    "SESSION_END_HOUR": 11,
    "RANGE_START_HOUR": 4,
    "RANGE_END_HOUR": 7,
    "RANGE_MAX_ATR": 0.0,
    "TOUCH_BUFFER_ATR": 0.05,
    "REJECT_CLOSE_EDGE": 0.60,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _bars_for_day_window(bars, day, start_hour, end_hour):
    out = []
    for bar in bars:
        moment = datetime.fromtimestamp(int(bar["time"]), tz=BKK)
        if moment.date() == day and start_hour <= moment.hour < end_hour:
            out.append(bar)
    return out


def detect_s231(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade only the first Asian-morning rejection of a rollover-range edge."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
        range_start = int(c["RANGE_START_HOUR"])
        range_end = int(c["RANGE_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < period + 12 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside Asian-morning session window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    today = dt_bkk.date()
    range_bars = _bars_for_day_window(
        bars[:-1], today, range_start, range_end
    )
    if len(range_bars) < 3:
        return _wait("Rollover range of today is not established")
    range_high = max(bar["high"] for bar in range_bars)
    range_low = min(bar["low"] for bar in range_bars)
    range_size = range_high - range_low
    if range_size <= 0.0:
        return _wait("Rollover range is degenerate")
    range_cap = float(c["RANGE_MAX_ATR"])
    if range_cap > 0.0 and range_size > atr * range_cap:
        return _wait("Rollover range is too wide")

    signal_bar = bars[-1]
    bar_range = signal_bar["high"] - signal_bar["low"]
    if bar_range <= 0.0:
        return _wait("Signal bar range is zero")
    touch = atr * float(c["TOUCH_BUFFER_ATR"])
    close_location = (signal_bar["close"] - signal_bar["low"]) / bar_range
    edge = float(c["REJECT_CLOSE_EDGE"])
    if (
        signal_bar["high"] >= range_high - touch
        and signal_bar["close"] < range_high
        and close_location <= 1.0 - edge
    ):
        side = -1
    elif (
        signal_bar["low"] <= range_low + touch
        and signal_bar["close"] > range_low
        and close_location >= edge
    ):
        side = 1
    else:
        return _wait("No rejected touch of the rollover range edge")

    # Any earlier Asian-session touch consumes that side's level, even if the
    # touch did not form a sufficiently strong rejection candle.
    earlier_asian = _bars_for_day_window(
        bars[:-1], today, start_hour, end_hour
    )
    if side > 0 and any(bar["low"] <= range_low + touch for bar in earlier_asian):
        return _wait("Lower rollover edge was already touched today")
    if side < 0 and any(bar["high"] >= range_high - touch for bar in earlier_asian):
        return _wait("Upper rollover edge was already touched today")

    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(signal_bar["close"], 2)
    if side > 0:
        sl = math.floor((signal_bar["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((signal_bar["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"First-rejection risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("First-rejection risk too large versus price")

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
        "pattern": f"S231 {signal} First Rollover-Edge Reject {rr:g}R",
        "reason": (
            f"First Asian rejection of today's {range_size:.2f} rollover range"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
