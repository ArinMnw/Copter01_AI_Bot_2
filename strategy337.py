# -*- coding: utf-8 -*-
"""S337 - Fair-value crossing-collapse release.

S337 measures how often closed prices cross their sample median.  A sharp
recent decline from a disjoint baseline means the auction has stopped rotating
around fair value and is persisting on one side, consistent with value-area
migration.  Direction comes from the fully closed recent path and its terminal
median displacement.

All inputs precede or equal the closed release candle as documented below.
Entry is next-open market, SL is beyond the release extreme plus ATR, and TP is
at least 7R.
"""

from __future__ import annotations

import math
from statistics import median

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 64,
    "RECENT_BARS": 20,
    "RECENT_CROSSING_RATE_MAX": 0.25,
    "CROSSING_RATE_DROP_MIN": 0.12,
    "TERMINAL_MEDIAN_DISTANCE_ATR_MIN": 0.45,
    "PATH_EFFICIENCY_MIN": 0.22,
    "NET_MOVE_ATR_MIN": 0.55,
    "RELEASE_BODY_ATR_MIN": 0.72,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.80,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 8.0,
    "BE_RR": 0.08,
    "CANCEL_BARS": 3,
}


def _median_crossing_profile(bars):
    closes = [float(bar["close"]) for bar in bars]
    if (
        len(closes) < 8
        or any(not math.isfinite(value) for value in closes)
    ):
        return None
    centre = median(closes)
    signs = []
    previous_sign = 0
    for value in closes:
        raw_sign = 1 if value > centre else (-1 if value < centre else 0)
        if raw_sign == 0:
            raw_sign = previous_sign
        if raw_sign != 0:
            signs.append(raw_sign)
            previous_sign = raw_sign
    if len(signs) < 2:
        return None
    crossings = sum(
        signs[index] != signs[index - 1]
        for index in range(1, len(signs))
    )
    return crossings / (len(signs) - 1), centre


def detect_s337(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after median-crossing activity collapses."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        recent_crossing_max = float(c["RECENT_CROSSING_RATE_MAX"])
        crossing_drop_min = float(c["CROSSING_RATE_DROP_MIN"])
        terminal_distance_min = float(
            c["TERMINAL_MEDIAN_DISTANCE_ATR_MIN"]
        )
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (
            recent_crossing_max,
            crossing_drop_min,
            terminal_distance_min,
        )
    ):
        return _wait("Invalid config: crossing gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        baseline_profile = _median_crossing_profile(baseline)
        recent_profile = _median_crossing_profile(recent)
        atr = _atr(bars[:-1], period)
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        ZeroDivisionError,
        AttributeError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    if baseline_profile is None or recent_profile is None:
        return _wait("Median-crossing profile is unavailable")

    baseline_crossing, _ = baseline_profile
    recent_crossing, recent_median = recent_profile
    crossing_drop = baseline_crossing - recent_crossing
    if (
        recent_crossing > recent_crossing_max
        or crossing_drop < crossing_drop_min
    ):
        return _wait(
            f"No fair-value crossing collapse "
            f"({baseline_crossing:.3f}->{recent_crossing:.3f}, "
            f"drop={crossing_drop:.3f})"
        )

    net_move = recent[-1]["close"] - recent[0]["close"]
    terminal_displacement = recent[-1]["close"] - recent_median
    travelled = sum(
        abs(recent[index]["close"] - recent[index - 1]["close"])
        for index in range(1, len(recent))
    )
    if travelled <= 0.0 or terminal_displacement == 0.0:
        return _wait("Recent path has no directional displacement")
    side = 1 if terminal_displacement > 0.0 else -1
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move is too small")
    if net_move * side <= 0.0:
        return _wait("Recent path opposes median displacement")
    if abs(terminal_displacement) < atr * terminal_distance_min:
        return _wait("Terminal median displacement is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes value-migration direction")
    if abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if candle_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    close_fraction = (
        (event["close"] - event["low"]) / candle_range
        if side > 0
        else (event["high"] - event["close"]) / candle_range
    )
    if close_fraction < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Release lacks directional close control")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(event["close"], 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor(
            (event["low"] - sl_buffer + 1e-12) * 100.0
        ) / 100.0
    else:
        sl = math.ceil(
            (event["high"] + sl_buffer - 1e-12) * 100.0
        ) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Release risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Release risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    tp = (
        math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
        if side > 0
        else math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    )
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S337 {signal} Fair-Value Migration {rr:g}R",
        "reason": (
            f"median crossings {baseline_crossing:.4f}->"
            f"{recent_crossing:.4f}, drop={crossing_drop:.4f}, "
            f"terminal={terminal_displacement / atr:.4f}ATR"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
