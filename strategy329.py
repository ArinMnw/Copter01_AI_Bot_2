# -*- coding: utf-8 -*-
"""S329 - Brownian-bridge path-coherence release.

For each return block, the cumulative path is detrended by the straight bridge
between its endpoints.  Residual bridge energy, normalized by realized return
energy, measures how far the path wanders around its net displacement.  S329
requires the recent bridge deviation to collapse relative to equal-length
baseline blocks before following a strong closed release.

All path inputs precede the release candle.  Entry is next-open market, the
stop is beyond the release extreme plus ATR, and TP is at least 7R.
"""

from __future__ import annotations

import math
from statistics import median

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 48,
    "RECENT_RETURNS": 16,
    "COHERENCE_RATIO_MAX": 0.65,
    "RECENT_BRIDGE_MAX": 0.80,
    "PATH_EFFICIENCY_MIN": 0.28,
    "NET_MOVE_ATR_MIN": 0.65,
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


def _closed_returns(bars):
    values = []
    for index in range(1, len(bars)):
        previous = float(bars[index - 1]["close"])
        current = float(bars[index]["close"])
        if previous <= 0.0 or current <= 0.0:
            return None
        values.append(math.log(current / previous))
    return values


def _bridge_deviation(returns):
    if len(returns) < 6:
        return None
    total = sum(returns)
    realized_energy = sum(value * value for value in returns)
    if realized_energy <= 0.0:
        return None
    cumulative = residual_square_sum = 0.0
    for index, value in enumerate(returns, 1):
        cumulative += value
        expected = total * index / len(returns)
        residual = cumulative - expected
        residual_square_sum += residual * residual
    residual_rms = math.sqrt(residual_square_sum / len(returns))
    return residual_rms / math.sqrt(realized_energy)


def detect_s329(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release when recent path wandering collapses."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        recent_count = max(6, int(c["RECENT_RETURNS"]))
        baseline_count = max(
            recent_count * 2, int(c["BASELINE_RETURNS"])
        )
        ratio_max = float(c["COHERENCE_RATIO_MAX"])
        bridge_max = float(c["RECENT_BRIDGE_MAX"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and value > 0.0
        for value in (ratio_max, bridge_max)
    ):
        return _wait("Invalid config: bridge gates must be positive and finite")

    required = max(period + 5, baseline_count + recent_count + 3)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 2:-1]
        returns = _closed_returns(history)
        baseline_returns = returns[:baseline_count]
        recent_returns = returns[baseline_count:]
        baseline_blocks = [
            baseline_returns[start:start + recent_count]
            for start in range(
                baseline_count - recent_count,
                -1,
                -recent_count,
            )
            if start + recent_count <= len(baseline_returns)
        ]
        baseline_deviations = [
            _bridge_deviation(block) for block in baseline_blocks
        ]
        baseline_deviations = [
            value for value in baseline_deviations if value is not None
        ]
        recent_deviation = _bridge_deviation(recent_returns)
        baseline_deviation = (
            median(baseline_deviations)
            if baseline_deviations else None
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
    if (
        baseline_deviation is None
        or recent_deviation is None
        or baseline_deviation <= 0.0
    ):
        return _wait("Bridge coherence is unavailable")
    coherence_ratio = recent_deviation / baseline_deviation
    if recent_deviation > bridge_max or coherence_ratio > ratio_max:
        return _wait(
            f"No bridge-coherence collapse ({recent_deviation:.3f}, "
            f"ratio={coherence_ratio:.3f})"
        )

    recent = history[baseline_count:]
    net_move = recent[-1]["close"] - recent[0]["close"]
    travelled = sum(
        abs(recent[index]["close"] - recent[index -1]["close"])
        for index in range(1, len(recent))
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
        return _wait("Release opposes coherent path")
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
        "pattern": f"S329 {signal} Brownian-Bridge Coherence {rr:g}R",
        "reason": (
            f"bridge deviation {baseline_deviation:.4f}->"
            f"{recent_deviation:.4f}, ratio={coherence_ratio:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
