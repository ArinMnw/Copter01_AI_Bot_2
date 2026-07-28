# -*- coding: utf-8 -*-
"""S214 - Previous-week high/low rejection reversal with a bar stop, 10R."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from strategy119 import _atr, _bars
from strategy197 import _wait


BKK = timezone(timedelta(hours=7))

DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "TOUCH_BUFFER_ATR": 0.05,
    "REJECT_CLOSE_EDGE": 0.60,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _previous_week_extremes(bars):
    """High/low of the most recent fully completed ISO week (BKK time)."""
    latest_week = None
    highs = {}
    lows = {}
    for bar in bars:
        moment = datetime.fromtimestamp(int(bar["time"]), tz=BKK)
        week = moment.isocalendar()[:2]
        highs[week] = max(highs.get(week, bar["high"]), bar["high"])
        lows[week] = min(lows.get(week, bar["low"]), bar["low"])
        latest_week = week
    weeks = sorted(highs)
    if latest_week is None or len(weeks) < 2:
        return None
    previous = weeks[-2]
    if previous == latest_week:
        return None
    return highs[previous], lows[previous]


def detect_s214(rates, tf, dt_bkk, cfg):
    """Fade a rejected test of the previous week's high or low."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < period + 8 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    extremes = _previous_week_extremes(bars[:-1])
    if extremes is None:
        return _wait("Window does not cover a completed previous week")
    week_high, week_low = extremes

    signal_bar = bars[-1]
    bar_range = signal_bar["high"] - signal_bar["low"]
    if bar_range <= 0.0:
        return _wait("Signal bar range is zero")
    touch = atr * float(c["TOUCH_BUFFER_ATR"])
    close_location = (signal_bar["close"] - signal_bar["low"]) / bar_range
    edge = float(c["REJECT_CLOSE_EDGE"])
    if (signal_bar["high"] >= week_high - touch
            and signal_bar["close"] < week_high
            and close_location <= 1.0 - edge):
        side = -1
    elif (signal_bar["low"] <= week_low + touch
            and signal_bar["close"] > week_low
            and close_location >= edge):
        side = 1
    else:
        return _wait("No rejected test of the previous-week extreme")

    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(signal_bar["close"], 2)
    if side > 0:
        sl = math.floor((signal_bar["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((signal_bar["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Rejection risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Rejection risk too large versus price")

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
        "pattern": f"S214 {signal} Prev-Week Extreme Reject {rr:g}R",
        "reason": (f"Rejected test of prev-week "
                   f"{'low' if side > 0 else 'high'}"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
