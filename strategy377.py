# -*- coding: utf-8 -*-
"""S377 — Second-Order Sign-Transition Forecast.

The detector estimates a closed-bar second-order Markov transition:
P(next return sign | previous two return signs).  The current two-sign
context must have enough recent support, a strong posterior directional
edge, and an improvement over an older disjoint baseline.  The resulting
forecast is executed by the caller at the next bar open.

Only supplied closed bars are inspected.  Stops are derived from the latest
closed event candle plus ATR, never from fixed points or future prices.
"""

from __future__ import annotations

import math


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 30,
    "RECENT_SUPPORT_MIN": 4,
    "BASELINE_SUPPORT_MIN": 6,
    "POSTERIOR_EDGE_MIN": 0.16,
    "EDGE_EXPANSION_MIN": 0.06,
    "CONTEXT_IMBALANCE_MIN": 0.20,
    "EVENT_BODY_ATR_MIN": 0.18,
    "EVENT_RANGE_ATR_MIN": 0.55,
    "EVENT_BODY_FRACTION_MIN": 0.35,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_CONTINUATION": True,
    "ALLOW_REVERSAL": True,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 7.0,
    "BE_RR": 0.05,
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


def _atr(bars, period):
    if period < 1 or len(bars) < period + 1:
        return 0.0
    values = []
    for index in range(len(bars) - period, len(bars)):
        bar = bars[index]
        previous_close = bars[index - 1]["close"]
        values.append(max(
            bar["high"] - bar["low"],
            abs(bar["high"] - previous_close),
            abs(bar["low"] - previous_close),
        ))
    return sum(values) / len(values)


def _signs(bars):
    result = []
    for index in range(1, len(bars)):
        change = bars[index]["close"] - bars[index - 1]["close"]
        result.append(1 if change > 0.0 else -1 if change < 0.0 else 0)
    return result


def _transition_profile(bars, context):
    signs = _signs(bars)
    positive = negative = 0
    for index in range(2, len(signs)):
        if (signs[index - 2], signs[index - 1]) != context:
            continue
        if signs[index] > 0:
            positive += 1
        elif signs[index] < 0:
            negative += 1
    support = positive + negative
    probability_up = (positive + 1.0) / (support + 2.0)
    return probability_up, support


def detect_s377(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S377 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(16, int(c["RECENT_BARS"]))
        recent_support_min = max(1, int(c["RECENT_SUPPORT_MIN"]))
        baseline_support_min = max(1, int(c["BASELINE_SUPPORT_MIN"]))
        posterior_edge_min = float(c["POSTERIOR_EDGE_MIN"])
        edge_expansion_min = float(c["EDGE_EXPANSION_MIN"])
        context_imbalance_min = float(c["CONTEXT_IMBALANCE_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (
            posterior_edge_min,
            edge_expansion_min,
            context_imbalance_min,
        )
    ):
        return _wait("Invalid config: transition gates are invalid")

    required = max(period + 3, baseline_count + recent_count + 2)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates[-required:])
        event = bars[-1]
        context_signs = _signs(bars[-3:])
        if len(context_signs) != 2 or 0 in context_signs:
            return _wait("Current two-bar sign context is flat")
        context = (context_signs[0], context_signs[1])
        history = bars[-baseline_count - recent_count - 2:-2]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        baseline_probability, baseline_support = _transition_profile(
            baseline,
            context,
        )
        recent_probability, recent_support = _transition_profile(
            recent,
            context,
        )
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
    if recent_support < recent_support_min:
        return _wait(f"Recent context support is sparse ({recent_support})")
    if baseline_support < baseline_support_min:
        return _wait(f"Baseline context support is sparse ({baseline_support})")

    recent_edge = abs(recent_probability - 0.5)
    baseline_edge = abs(baseline_probability - 0.5)
    if recent_edge < posterior_edge_min:
        return _wait(f"Recent posterior edge is weak ({recent_edge:.3f})")
    if recent_edge - baseline_edge < edge_expansion_min:
        return _wait(
            f"No transition-edge expansion ({recent_edge - baseline_edge:.3f})"
        )
    context_imbalance = abs(sum(context)) / 2.0
    if context_imbalance < context_imbalance_min:
        return _wait("Two-bar context lacks directional imbalance")

    body = float(event["close"]) - float(event["open"])
    candle_range = float(event["high"]) - float(event["low"])
    if body == 0.0 or candle_range <= 0.0:
        return _wait("Event candle is flat")
    if abs(body) < atr * float(c["EVENT_BODY_ATR_MIN"]):
        return _wait("Event body is too small versus ATR")
    if candle_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Event range is too small versus ATR")
    if abs(body) / candle_range < float(c["EVENT_BODY_FRACTION_MIN"]):
        return _wait("Event candle lacks body control")

    side = 1 if recent_probability > 0.5 else -1
    signal = "BUY" if side > 0 else "SELL"
    event_side = 1 if body > 0.0 else -1
    mode = "continuation" if side == event_side else "reversal"
    if mode == "continuation" and not bool(c["ALLOW_CONTINUATION"]):
        return _wait("Continuation mode disabled")
    if mode == "reversal" and not bool(c["ALLOW_REVERSAL"]):
        return _wait("Reversal mode disabled")
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
        "pattern": f"S377 {signal} Markov Forecast {rr:g}R",
        "reason": (
            f"{mode} context={context}, "
            f"posterior={recent_probability:.4f}, "
            f"edge expansion={recent_edge - baseline_edge:.4f}, "
            f"support={recent_support}/{baseline_support}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
