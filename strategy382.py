# -*- coding: utf-8 -*-
"""S382 — Spearman Volume-Range Coupling Release.

The detector measures rank correlation between tick volume and true range.
Recent positive coupling must strengthen over older disjoint blocks, showing
that participation is translating efficiently into price travel. Directional
volume, net displacement, and a controlled event candle then release with the
auction direction at the next bar open.

Only supplied closed bars are inspected. The event extreme plus ATR defines
dynamic risk; no fixed-point stop or future price is used.
"""

from __future__ import annotations

import math
import statistics


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 80,
    "RECENT_BARS": 28,
    "RECENT_CORRELATION_MIN": 0.30,
    "CORRELATION_RISE_MIN": 0.10,
    "DIRECTIONAL_VOLUME_MIN": 0.15,
    "PATH_EFFICIENCY_MIN": 0.20,
    "NET_MOVE_ATR_MIN": 0.45,
    "EVENT_VOLUME_RATIO_MIN": 1.15,
    "EVENT_BODY_ATR_MIN": 0.50,
    "EVENT_RANGE_ATR_MIN": 0.70,
    "EVENT_BODY_FRACTION_MIN": 0.70,
    "EVENT_CLOSE_FRACTION": 0.75,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.16,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 7.0,
    "BE_RR": 0.01,
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


def _rank(values):
    order = sorted(range(len(values)), key=lambda index: values[index])
    result = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average_rank = (start + end - 1.0) / 2.0
        for position in range(start, end):
            result[order[position]] = average_rank
        start = end
    return result


def _pearson(left, right):
    if len(left) != len(right) or len(left) < 6:
        return None
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    left_delta = [value - left_mean for value in left]
    right_delta = [value - right_mean for value in right]
    left_energy = sum(value * value for value in left_delta)
    right_energy = sum(value * value for value in right_delta)
    if left_energy <= 0.0 or right_energy <= 0.0:
        return None
    covariance = sum(a * b for a, b in zip(left_delta, right_delta))
    return covariance / math.sqrt(left_energy * right_energy)


def _profile(bars):
    if len(bars) < 8:
        return None
    volumes = []
    ranges = []
    signed_volume = 0.0
    total_volume = 0.0
    travelled = 0.0
    for index in range(1, len(bars)):
        bar = bars[index]
        previous_close = bars[index - 1]["close"]
        true_range = max(
            bar["high"] - bar["low"],
            abs(bar["high"] - previous_close),
            abs(bar["low"] - previous_close),
        )
        volume = bar["tick_volume"]
        body = bar["close"] - bar["open"]
        volumes.append(volume)
        ranges.append(true_range)
        if body != 0.0:
            signed_volume += (1.0 if body > 0.0 else -1.0) * volume
        total_volume += volume
        travelled += abs(bar["close"] - previous_close)
    correlation = _pearson(_rank(volumes), _rank(ranges))
    if correlation is None or total_volume <= 0.0 or travelled <= 0.0:
        return None
    net_move = bars[-1]["close"] - bars[0]["close"]
    return (
        correlation,
        signed_volume / total_volume,
        abs(net_move) / travelled,
        net_move,
        statistics.median(volumes),
    )


def detect_s382(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S382 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(10, int(c["RECENT_BARS"]))
        recent_correlation_min = float(c["RECENT_CORRELATION_MIN"])
        correlation_rise_min = float(c["CORRELATION_RISE_MIN"])
        directional_volume_min = float(c["DIRECTIONAL_VOLUME_MIN"])
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
            recent_correlation_min,
            correlation_rise_min,
            directional_volume_min,
            path_min,
            net_move_min,
        )
    ):
        return _wait("Invalid config: coupling gates are invalid")

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
        baseline_correlations = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _profile(baseline[start:start + recent_count])
            if profile is not None:
                baseline_correlations.append(profile[0])
        recent_profile = _profile(recent)
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
    if recent_profile is None or not baseline_correlations:
        return _wait("Volume-range rank profile is unavailable")

    correlation, directional_volume, path_efficiency, net_move, median_volume = recent_profile
    baseline_correlation = statistics.median(baseline_correlations)
    correlation_rise = correlation - baseline_correlation
    if correlation < recent_correlation_min:
        return _wait(f"Volume-range coupling is weak ({correlation:.3f})")
    if correlation_rise < correlation_rise_min:
        return _wait(f"No coupling expansion ({correlation_rise:.3f})")
    if abs(directional_volume) < directional_volume_min:
        return _wait(f"Directional volume imbalance is weak ({directional_volume:.3f})")
    if path_efficiency < path_min:
        return _wait(f"Auction path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Auction net move is too small versus ATR")
    side = 1 if net_move > 0.0 else -1
    if side * directional_volume <= 0.0:
        return _wait("Net move and directional volume disagree")

    body = float(event["close"]) - float(event["open"])
    candle_range = float(event["high"]) - float(event["low"])
    if body == 0.0 or candle_range <= 0.0:
        return _wait("Event release is flat")
    if side * body <= 0.0:
        return _wait("Event does not align with coupled auction")
    volume_ratio = float(event["tick_volume"]) / median_volume
    if volume_ratio < float(c["EVENT_VOLUME_RATIO_MIN"]):
        return _wait(f"Event participation is weak ({volume_ratio:.3f}x)")
    if abs(body) < atr * float(c["EVENT_BODY_ATR_MIN"]):
        return _wait("Event body is too small versus ATR")
    if candle_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Event range is too small versus ATR")
    if abs(body) / candle_range < float(c["EVENT_BODY_FRACTION_MIN"]):
        return _wait("Event release lacks body control")
    if side > 0:
        location = (event["close"] - event["low"]) / candle_range
    else:
        location = (event["high"] - event["close"]) / candle_range
    if location < float(c["EVENT_CLOSE_FRACTION"]):
        return _wait(f"Event close lacks directional control ({location:.3f})")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(float(event["close"]), 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor((float(event["low"]) - sl_buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((float(event["high"]) + sl_buffer - 1e-12) * 100.0) / 100.0
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
        "pattern": f"S382 {signal} Rank-Coupling Release {rr:g}R",
        "reason": (
            f"Spearman={correlation:.4f}, rise={correlation_rise:.4f}, "
            f"directional volume={directional_volume:.4f}, "
            f"event volume={volume_ratio:.4f}x"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
