# -*- coding: utf-8 -*-
"""S355 - Arcsine extremum-time migration release.

S355 tracks where directional adverse and favorable extrema occur inside a
closed price window.  An early adverse extreme followed by a favorable extreme
near the window endpoint represents chronological price discovery, consistent
with endpoint-heavy extremum timing under arcsine geometry.

All extremum and path inputs precede the release candle.  Entry is next-open
market, SL is beyond the closed release extreme plus ATR, and TP is at least
7R.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 24,
    "FAVORABLE_TIME_MIN": 0.75,
    "ADVERSE_TIME_MAX": 0.20,
    "EXTREMUM_SPAN_MIN": 0.45,
    "SPAN_JUMP_MIN": 0.15,
    "PATH_EFFICIENCY_MIN": 0.30,
    "NET_MOVE_ATR_MIN": 0.60,
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
    "BE_RR": 0.05,
    "CANCEL_BARS": 3,
}


def _extremum_profile(bars):
    if len(bars) < 8:
        return None
    closes = [float(bar["close"]) for bar in bars]
    highs = [float(bar["high"]) for bar in bars]
    lows = [float(bar["low"]) for bar in bars]
    if not all(
        math.isfinite(value)
        for value in closes + highs + lows
    ):
        return None
    net_move = closes[-1] - closes[0]
    if abs(net_move) <= 1e-12:
        return None
    side = 1 if net_move > 0.0 else -1
    if side > 0:
        favorable_value = max(highs)
        adverse_value = min(lows)
        favorable_index = max(
            index for index, value in enumerate(highs)
            if value == favorable_value
        )
        adverse_index = min(
            index for index, value in enumerate(lows)
            if value == adverse_value
        )
    else:
        favorable_value = min(lows)
        adverse_value = max(highs)
        favorable_index = max(
            index for index, value in enumerate(lows)
            if value == favorable_value
        )
        adverse_index = min(
            index for index, value in enumerate(highs)
            if value == adverse_value
        )
    denominator = len(bars) - 1
    favorable_time = favorable_index / denominator
    adverse_time = adverse_index / denominator
    span = favorable_time - adverse_time
    travelled = sum(
        abs(closes[index] - closes[index - 1])
        for index in range(1, len(closes))
    )
    if travelled <= 0.0:
        return None
    efficiency = abs(net_move) / travelled
    return (
        favorable_time,
        adverse_time,
        span,
        side,
        net_move,
        efficiency,
    )


def detect_s355(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow chronological migration from adverse to favorable extreme."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        favorable_time_min = float(c["FAVORABLE_TIME_MIN"])
        adverse_time_max = float(c["ADVERSE_TIME_MAX"])
        span_min = float(c["EXTREMUM_SPAN_MIN"])
        span_jump_min = float(c["SPAN_JUMP_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (
            favorable_time_min,
            adverse_time_max,
            span_min,
            span_jump_min,
        )
    ):
        return _wait("Invalid config: extremum-time gates are invalid")

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
        baseline_spans = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _extremum_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_spans.append(profile[2])
        recent_profile = _extremum_profile(recent)
        atr = _atr(bars[:-1], period)
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        ZeroDivisionError,
        AttributeError,
        statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    if recent_profile is None or not baseline_spans:
        return _wait("Extremum-time profile is unavailable")

    favorable_time, adverse_time, span, side, net_move, efficiency = (
        recent_profile
    )
    baseline_span = statistics.median(baseline_spans)
    span_jump = span - baseline_span
    if (
        favorable_time < favorable_time_min
        or adverse_time > adverse_time_max
        or span < span_min
        or span_jump < span_jump_min
    ):
        return _wait(
            f"No extremum-time migration "
            f"(fav={favorable_time:.3f}, adv={adverse_time:.3f}, "
            f"span={baseline_span:.3f}->{span:.3f}, jump={span_jump:.3f})"
        )
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Extremum path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Extremum net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes extremum migration")
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
        "pattern": f"S355 {signal} Extremum Migration {rr:g}R",
        "reason": (
            f"extremum times adv={adverse_time:.4f}, "
            f"fav={favorable_time:.4f}, span={baseline_span:.4f}->"
            f"{span:.4f}, jump={span_jump:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
