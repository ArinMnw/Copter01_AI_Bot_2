# -*- coding: utf-8 -*-
"""S381 — Spearman Volume-Range Decoupling Reversal.

The detector measures the rank correlation between tick volume and true range.
A sharp recent correlation deterioration versus older disjoint blocks signals
that participation no longer produces proportional price travel. Directional
volume and net displacement define the exhausted auction; a closed rejection
against that auction triggers a next-open market fade.

Only supplied closed bars are inspected. The rejection extreme plus ATR
defines dynamic risk, with no fixed-point stop or future-price access.
"""

from __future__ import annotations

import math
import statistics


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 60,
    "RECENT_BARS": 20,
    "RECENT_CORRELATION_MAX": 0.10,
    "CORRELATION_DROP_MIN": 0.25,
    "DIRECTIONAL_VOLUME_MIN": 0.15,
    "PATH_EFFICIENCY_MIN": 0.12,
    "NET_MOVE_ATR_MIN": 0.40,
    "REJECTION_VOLUME_RATIO_MIN": 0.90,
    "REJECTION_BODY_ATR_MIN": 0.15,
    "REJECTION_RANGE_ATR_MIN": 0.70,
    "REJECTION_WICK_FRACTION_MIN": 0.25,
    "REJECTION_CLOSE_FRACTION": 0.55,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 7.0,
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


def detect_s381(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S381 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(10, int(c["RECENT_BARS"]))
        recent_correlation_max = float(c["RECENT_CORRELATION_MAX"])
        correlation_drop_min = float(c["CORRELATION_DROP_MIN"])
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
            correlation_drop_min,
            directional_volume_min,
            path_min,
            net_move_min,
        )
    ) or not math.isfinite(recent_correlation_max):
        return _wait("Invalid config: decoupling gates are invalid")

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
    correlation_drop = baseline_correlation - correlation
    if correlation > recent_correlation_max:
        return _wait(f"Volume-range coupling remains strong ({correlation:.3f})")
    if correlation_drop < correlation_drop_min:
        return _wait(f"No correlation deterioration ({correlation_drop:.3f})")
    if abs(directional_volume) < directional_volume_min:
        return _wait(f"Directional volume imbalance is weak ({directional_volume:.3f})")
    if path_efficiency < path_min:
        return _wait(f"Auction path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Auction net move is too small versus ATR")
    auction_side = 1 if net_move > 0.0 else -1
    if auction_side * directional_volume <= 0.0:
        return _wait("Net move and directional volume disagree")

    body = float(event["close"]) - float(event["open"])
    candle_range = float(event["high"]) - float(event["low"])
    if body == 0.0 or candle_range <= 0.0:
        return _wait("Rejection candle is flat")
    side = -auction_side
    if side * body <= 0.0:
        return _wait("No rejection against exhausted auction")
    volume_ratio = float(event["tick_volume"]) / median_volume
    if volume_ratio < float(c["REJECTION_VOLUME_RATIO_MIN"]):
        return _wait(f"Rejection participation is weak ({volume_ratio:.3f}x)")
    if abs(body) < atr * float(c["REJECTION_BODY_ATR_MIN"]):
        return _wait("Rejection body is too small versus ATR")
    if candle_range < atr * float(c["REJECTION_RANGE_ATR_MIN"]):
        return _wait("Rejection range is too small versus ATR")

    if side > 0:
        rejection_wick = min(event["open"], event["close"]) - event["low"]
        location = (event["close"] - event["low"]) / candle_range
    else:
        rejection_wick = event["high"] - max(event["open"], event["close"])
        location = (event["high"] - event["close"]) / candle_range
    if rejection_wick / candle_range < float(c["REJECTION_WICK_FRACTION_MIN"]):
        return _wait("Rejection wick is too small")
    if location < float(c["REJECTION_CLOSE_FRACTION"]):
        return _wait(f"Rejection close lacks control ({location:.3f})")

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
        return _wait(f"Rejection risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Rejection risk too large versus price")

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
        "pattern": f"S381 {signal} Rank-Decoupling Reversal {rr:g}R",
        "reason": (
            f"Spearman={correlation:.4f}, drop={correlation_drop:.4f}, "
            f"directional volume={directional_volume:.4f}, "
            f"rejection volume={volume_ratio:.4f}x"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
