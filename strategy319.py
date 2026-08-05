# -*- coding: utf-8 -*-
"""S319 - Higuchi fractal-dimension collapse release.

Higuchi dimension estimates path roughness directly across several sampling
scales.  S319 follows a structural release only when a rough baseline changes
to a lower-dimensional, directionally efficient recent path.  This is a
geometric regime measure rather than a return-distribution statistic, entropy
count, or linear trend estimate.

Both dimension samples precede the current closed release candle.  Execution
is next-open market with a release-extreme ATR stop and TP of at least 7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 64,
    "RECENT_BARS": 32,
    "HIGUCHI_K_MAX": 5,
    "BASELINE_DIMENSION_MIN": 1.25,
    "RECENT_DIMENSION_MAX": 1.55,
    "DIMENSION_DROP_MIN": 0.06,
    "PATH_EFFICIENCY_MIN": 0.30,
    "NET_MOVE_ATR_MIN": 0.70,
    "BREAKOUT_LOOKBACK": 10,
    "BREAKOUT_BUFFER_ATR": 0.01,
    "RELEASE_BODY_ATR_MIN": 0.60,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.80,
    "SESSION_START_HOUR": 7,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 8.0,
    "BE_RR": 0.10,
    "CANCEL_BARS": 3,
}


def _higuchi_dimension(values, k_max):
    size = len(values)
    if size < max(12, k_max * 2 + 1):
        return None
    x_values, y_values = [], []
    for step in range(1, k_max + 1):
        component_lengths = []
        for offset in range(step):
            intervals = (size - 1 - offset) // step
            if intervals < 1:
                continue
            path_length = sum(
                abs(
                    values[offset + index * step]
                    - values[offset + (index - 1) * step]
                )
                for index in range(1, intervals + 1)
            )
            normalization = (size - 1) / (intervals * step)
            component_lengths.append(path_length * normalization / step)
        if not component_lengths:
            continue
        average_length = sum(component_lengths) / len(component_lengths)
        if average_length <= 0.0:
            continue
        x_values.append(math.log(1.0 / step))
        y_values.append(math.log(average_length))
    if len(x_values) < 3:
        return None
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    denominator = sum((value - x_mean) ** 2 for value in x_values)
    if denominator <= 0.0:
        return None
    return sum(
        (x_values[index] - x_mean) * (y_values[index] - y_mean)
        for index in range(len(x_values))
    ) / denominator


def detect_s319(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a structural release after fractal-dimension collapse."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        k_max = max(2, int(c["HIGUCHI_K_MAX"]))
        breakout_lookback = max(3, int(c["BREAKOUT_LOOKBACK"]))
        baseline_min = float(c["BASELINE_DIMENSION_MIN"])
        recent_max = float(c["RECENT_DIMENSION_MAX"])
        drop_min = float(c["DIMENSION_DROP_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if k_max > min(baseline_count, recent_count) // 2:
        return _wait("Invalid config: HIGUCHI_K_MAX is too large")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (baseline_min, recent_max, drop_min)
    ):
        return _wait("Invalid config: dimension thresholds must be finite")

    required = max(
        baseline_count + recent_count + 3,
        period + breakout_lookback + 5,
    )
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside liquid session")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline_closes = [
            bar["close"] for bar in history[:baseline_count]
        ]
        recent_bars = history[baseline_count:]
        recent_closes = [bar["close"] for bar in recent_bars]
        baseline_dimension = _higuchi_dimension(baseline_closes, k_max)
        recent_dimension = _higuchi_dimension(recent_closes, k_max)
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
    if baseline_dimension is None or recent_dimension is None:
        return _wait("Higuchi dimension is unavailable")
    dimension_drop = baseline_dimension - recent_dimension
    if baseline_dimension < baseline_min:
        return _wait(f"Baseline path is already smooth ({baseline_dimension:.3f})")
    if recent_dimension > recent_max or dimension_drop < drop_min:
        return _wait(
            f"No dimension collapse ({recent_dimension:.3f}, "
            f"drop={dimension_drop:.3f})"
        )

    net_move = recent_closes[-1] - recent_closes[0]
    travelled = sum(
        abs(recent_closes[index] - recent_closes[index - 1])
        for index in range(1, len(recent_closes))
    )
    if travelled <= 0.0:
        return _wait("Recent path has no movement")
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move is too small")
    side = 1 if net_move > 0.0 else -1

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes the smooth path")
    if abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if candle_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    structure = bars[-breakout_lookback - 1:-1]
    buffer = atr * float(c["BREAKOUT_BUFFER_ATR"])
    if side > 0:
        structure_level = max(bar["high"] for bar in structure)
        close_fraction = (event["close"] - event["low"]) / candle_range
        if event["close"] <= structure_level + buffer:
            return _wait("BUY release does not break structure")
    else:
        structure_level = min(bar["low"] for bar in structure)
        close_fraction = (event["high"] - event["close"]) / candle_range
        if event["close"] >= structure_level - buffer:
            return _wait("SELL release does not break structure")
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
        sl = math.floor((event["low"] - sl_buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + sl_buffer - 1e-12) * 100.0) / 100.0
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
        "pattern": f"S319 {signal} Higuchi Dimension Release {rr:g}R",
        "reason": (
            f"Higuchi dimension {baseline_dimension:.4f}->"
            f"{recent_dimension:.4f}, efficiency={efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
