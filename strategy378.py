# -*- coding: utf-8 -*-
"""S378 — Volatility-State Persistence Release.

The detector models the first-order persistence of a high true-range state.
Recent P(high range at t+1 | high range at t) must be strong and expand over
an older disjoint baseline.  A closed, body-controlled high-range event then
supplies the release direction for a next-open market entry.

All calculations use supplied closed bars only.  The event extreme plus ATR
defines risk, so neither fixed-point stops nor future prices are used.
"""

from __future__ import annotations

import math
import statistics


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 30,
    "HIGH_RANGE_RATIO": 1.15,
    "RECENT_SUPPORT_MIN": 5,
    "BASELINE_SUPPORT_MIN": 10,
    "PERSISTENCE_MIN": 0.60,
    "PERSISTENCE_EXPANSION_MIN": 0.12,
    "EVENT_RANGE_RATIO_MIN": 1.20,
    "EVENT_BODY_ATR_MIN": 0.50,
    "EVENT_BODY_FRACTION_MIN": 0.55,
    "EVENT_CLOSE_FRACTION": 0.80,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.18,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 9.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite rate value")
    return number


def _bars(rates):
    result = []
    previous_time = None
    for raw in rates:
        timestamp = int(_finite(raw["time"]))
        if previous_time is not None and timestamp <= previous_time:
            raise ValueError("rates must be chronological")
        previous_time = timestamp
        bar = {
            "time": timestamp,
            "open": _finite(raw["open"]),
            "high": _finite(raw["high"]),
            "low": _finite(raw["low"]),
            "close": _finite(raw["close"]),
            "tick_volume": max(1.0, _finite(raw["tick_volume"])),
        }
        if bar["high"] < max(bar["open"], bar["close"], bar["low"]):
            raise ValueError("invalid high")
        if bar["low"] > min(bar["open"], bar["close"], bar["high"]):
            raise ValueError("invalid low")
        if min(bar["open"], bar["high"], bar["low"], bar["close"]) <= 0.0:
            raise ValueError("prices must be positive")
        result.append(bar)
    return result


def _true_ranges(bars):
    values = []
    for index in range(1, len(bars)):
        bar = bars[index]
        previous_close = bars[index - 1]["close"]
        values.append(max(
            bar["high"] - bar["low"],
            abs(bar["high"] - previous_close),
            abs(bar["low"] - previous_close),
        ))
    return values


def _atr(bars, period):
    values = _true_ranges(bars)
    if period < 1 or len(values) < period:
        return 0.0
    return sum(values[-period:]) / period


def _persistence(ranges, threshold):
    high_after_high = 0
    high_predecessors = 0
    for previous, current in zip(ranges, ranges[1:]):
        if previous < threshold:
            continue
        high_predecessors += 1
        if current >= threshold:
            high_after_high += 1
    probability = (high_after_high + 1.0) / (high_predecessors + 2.0)
    return probability, high_predecessors


def detect_s378(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S378 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(16, int(c["RECENT_BARS"]))
        high_range_ratio = float(c["HIGH_RANGE_RATIO"])
        recent_support_min = max(1, int(c["RECENT_SUPPORT_MIN"]))
        baseline_support_min = max(1, int(c["BASELINE_SUPPORT_MIN"]))
        persistence_min = float(c["PERSISTENCE_MIN"])
        persistence_expansion_min = float(c["PERSISTENCE_EXPANSION_MIN"])
        event_range_ratio_min = float(c["EVENT_RANGE_RATIO_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (
            high_range_ratio,
            persistence_min,
            persistence_expansion_min,
            event_range_ratio_min,
        )
    ):
        return _wait("Invalid config: volatility-state gates are invalid")

    required = max(period + 3, baseline_count + recent_count + 2)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates[-required:])
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        history_ranges = _true_ranges(history)
        baseline_ranges = history_ranges[:baseline_count - 1]
        recent_ranges = history_ranges[baseline_count - 1:]
        reference_range = statistics.median(baseline_ranges)
        threshold = reference_range * high_range_ratio
        baseline_persistence, baseline_support = _persistence(
            baseline_ranges,
            threshold,
        )
        recent_persistence, recent_support = _persistence(
            recent_ranges,
            threshold,
        )
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
    if atr <= 0.0 or reference_range <= 0.0:
        return _wait("ATR or reference range is zero")
    if recent_support < recent_support_min:
        return _wait(f"Recent high-state support is sparse ({recent_support})")
    if baseline_support < baseline_support_min:
        return _wait(f"Baseline high-state support is sparse ({baseline_support})")
    if recent_persistence < persistence_min:
        return _wait(
            f"Recent high-state persistence is weak ({recent_persistence:.3f})"
        )
    expansion = recent_persistence - baseline_persistence
    if expansion < persistence_expansion_min:
        return _wait(f"No persistence expansion ({expansion:.3f})")

    body = float(event["close"]) - float(event["open"])
    candle_range = float(event["high"]) - float(event["low"])
    event_range_ratio = candle_range / reference_range
    if body == 0.0 or candle_range <= 0.0:
        return _wait("Event release is flat")
    if event_range_ratio < event_range_ratio_min:
        return _wait(f"Event range state is weak ({event_range_ratio:.3f}x)")
    if abs(body) < atr * float(c["EVENT_BODY_ATR_MIN"]):
        return _wait("Event body is too small versus ATR")
    if abs(body) / candle_range < float(c["EVENT_BODY_FRACTION_MIN"]):
        return _wait("Event release lacks body control")

    close_fraction = float(c["EVENT_CLOSE_FRACTION"])
    side = 1 if body > 0.0 else -1
    if side > 0:
        location = (float(event["close"]) - float(event["low"])) / candle_range
    else:
        location = (float(event["high"]) - float(event["close"])) / candle_range
    if location < close_fraction:
        return _wait(f"Event close lacks directional control ({location:.3f})")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(float(event["close"]), 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor(
            (float(event["low"]) - sl_buffer + 1e-12) * 100.0
        ) / 100.0
    else:
        sl = math.ceil(
            (float(event["high"]) + sl_buffer - 1e-12) * 100.0
        ) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Event risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Event risk too large versus price")

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
        "pattern": f"S378 {signal} Volatility Persistence {rr:g}R",
        "reason": (
            f"persistence={recent_persistence:.4f}, "
            f"expansion={expansion:.4f}, "
            f"event range={event_range_ratio:.4f}x, "
            f"support={recent_support}/{baseline_support}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
