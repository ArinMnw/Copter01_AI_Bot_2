# -*- coding: utf-8 -*-
"""S305 - Rollover drive with HTF bias and robust participation, 10R.

S304 established that the 04:00-06:00 BKK rolling-range breakout remains
profitable across two six-month validation windows when it agrees with an
eight-hour price bias.  Its latest two-month loss, however, came from weak
breaks during a fade regime.  S305 changes one variable: a breakout is accepted
only when its tick volume is at least a configurable fraction of the median
volume in the preceding micro-range.

The median is intentional.  A single quote burst can inflate a mean and make an
otherwise normal breakout look inactive.  Median-relative participation asks a
more stable question: is the acting bar at least as busy as the local market?
This is an ablation of S304, not a claim that MT5 tick volume is true exchange
volume.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 4,
    "SESSION_END_HOUR": 6,
    "SESSION_WEEKDAY": -1,
    "RANGE_BARS": 8,
    "BREAK_BODY_MIN_FRACTION": 0.40,
    # 0 disables the new S305 ablation.  The initial value is deliberately
    # permissive so it removes only unusually quiet rollover breaks.
    "BREAK_VOLUME_MEDIAN_RATIO": 0.90,
    "RANGE_MAX_ATR": 0.0,
    "HTF_BIAS_BARS": 96,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s305(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a participation-confirmed rollover drive with HTF alignment."""
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
    required = max(range_bars + period + 6, int(c.get("HTF_BIAS_BARS", 0) or 0) + 2)
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

    volume_floor = float(c["BREAK_VOLUME_MEDIAN_RATIO"])
    if volume_floor > 0.0:
        baseline_volume = statistics.median(
            float(bar["tick_volume"]) for bar in micro_range
        )
        breakout_volume = float(breakout["tick_volume"])
        if baseline_volume <= 0.0 or breakout_volume < baseline_volume * volume_floor:
            return _wait("Drive lacks robust volume participation")
        volume_ratio = breakout_volume / baseline_volume
    else:
        volume_ratio = math.nan

    bias_bars = int(c.get("HTF_BIAS_BARS", 0) or 0)
    if bias_bars > 0:
        history = bars[-bias_bars - 1:-1]
        if len(history) < bias_bars:
            return _wait("Not enough history for the higher-timeframe bias")
        reference = sum(bar["close"] for bar in history) / len(history)
        if side > 0 and breakout["close"] <= reference:
            return _wait("Upward drive disagrees with the higher-timeframe bias")
        if side < 0 and breakout["close"] >= reference:
            return _wait("Downward drive disagrees with the higher-timeframe bias")

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
    volume_text = "off" if math.isnan(volume_ratio) else f"{volume_ratio:.2f}x"
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S305 {signal} Rollover Participation {rr:g}R",
        "reason": (
            f"Drive out of {range_size:.2f} micro range at rollover; "
            f"median-volume={volume_text}; risk={risk:.2f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
