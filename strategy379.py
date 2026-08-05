# -*- coding: utf-8 -*-
"""S379 — Wald-Wolfowitz Runs-Compression Release.

The detector applies a Wald-Wolfowitz runs statistic to closed return signs.
Too few recent sign runs versus the random-sequence expectation indicate
directional clustering.  That clustering must strengthen over disjoint older
blocks, have a directional/path imbalance, and end in a controlled release
candle aligned with the clustered move.

Only supplied closed bars are inspected.  The caller fills a market signal at
the next bar open; the event extreme plus ATR defines the stop.
"""

from __future__ import annotations

import math
import statistics


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 24,
    "CLUSTER_STRENGTH_MIN": 0.40,
    "CLUSTER_EXPANSION_MIN": 0.30,
    "SIGN_IMBALANCE_MIN": 0.20,
    "PATH_EFFICIENCY_MIN": 0.24,
    "NET_MOVE_ATR_MIN": 0.45,
    "EVENT_BODY_ATR_MIN": 0.60,
    "EVENT_RANGE_ATR_MIN": 0.80,
    "EVENT_BODY_FRACTION_MIN": 0.60,
    "EVENT_CLOSE_FRACTION": 0.75,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.12,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 8.0,
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


def _runs_profile(bars):
    changes = [
        bars[index]["close"] - bars[index - 1]["close"]
        for index in range(1, len(bars))
    ]
    signs = [
        1 if change > 0.0 else -1
        for change in changes
        if change != 0.0
    ]
    if len(signs) < 8:
        return None
    positive = sum(sign > 0 for sign in signs)
    negative = len(signs) - positive
    if positive == 0 or negative == 0:
        z_score = -math.sqrt(len(signs))
    else:
        runs = 1 + sum(
            left != right
            for left, right in zip(signs, signs[1:])
        )
        count = len(signs)
        expected = 1.0 + 2.0 * positive * negative / count
        variance = (
            2.0
            * positive
            * negative
            * (2.0 * positive * negative - count)
            / (count * count * (count - 1.0))
        )
        if variance <= 0.0:
            return None
        z_score = (runs - expected) / math.sqrt(variance)
    sign_imbalance = sum(signs) / len(signs)
    travelled = sum(abs(change) for change in changes)
    if travelled <= 0.0:
        return None
    net_move = bars[-1]["close"] - bars[0]["close"]
    path_efficiency = abs(net_move) / travelled
    return z_score, sign_imbalance, path_efficiency, net_move


def detect_s379(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S379 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        cluster_min = float(c["CLUSTER_STRENGTH_MIN"])
        expansion_min = float(c["CLUSTER_EXPANSION_MIN"])
        sign_imbalance_min = float(c["SIGN_IMBALANCE_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_move_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (
            cluster_min,
            expansion_min,
            sign_imbalance_min,
            path_min,
            net_move_min,
        )
    ):
        return _wait("Invalid config: runs gates are invalid")

    required = max(period + 3, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates[-required:])
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        baseline_strengths = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _runs_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_strengths.append(max(0.0, -profile[0]))
        recent_profile = _runs_profile(recent)
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
    if recent_profile is None or not baseline_strengths:
        return _wait("Runs profile is unavailable")

    z_score, sign_imbalance, path_efficiency, net_move = recent_profile
    cluster_strength = max(0.0, -z_score)
    baseline_strength = statistics.median(baseline_strengths)
    cluster_expansion = cluster_strength - baseline_strength
    if cluster_strength < cluster_min:
        return _wait(f"Sign clustering is weak ({cluster_strength:.3f})")
    if cluster_expansion < expansion_min:
        return _wait(f"No runs-compression expansion ({cluster_expansion:.3f})")
    if abs(sign_imbalance) < sign_imbalance_min:
        return _wait(f"Sign imbalance is weak ({sign_imbalance:.3f})")
    if path_efficiency < path_min:
        return _wait(f"Cluster path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Cluster net move is too small versus ATR")

    body = float(event["close"]) - float(event["open"])
    candle_range = float(event["high"]) - float(event["low"])
    if body == 0.0 or candle_range <= 0.0:
        return _wait("Event release is flat")
    if abs(body) < atr * float(c["EVENT_BODY_ATR_MIN"]):
        return _wait("Event body is too small versus ATR")
    if candle_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Event range is too small versus ATR")
    if abs(body) / candle_range < float(c["EVENT_BODY_FRACTION_MIN"]):
        return _wait("Event release lacks body control")

    side = 1 if net_move > 0.0 else -1
    if side * sign_imbalance <= 0.0 or side * body <= 0.0:
        return _wait("Event does not align with clustered direction")
    close_fraction = float(c["EVENT_CLOSE_FRACTION"])
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
        "pattern": f"S379 {signal} Runs Compression {rr:g}R",
        "reason": (
            f"runs z={z_score:.4f}, "
            f"cluster expansion={cluster_expansion:.4f}, "
            f"sign imbalance={sign_imbalance:.4f}, "
            f"path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
