# -*- coding: utf-8 -*-
"""S321 - BDS-style nonlinear-dependence release.

For iid returns, the two-dimensional correlation integral C2(epsilon) should
approximately equal C1(epsilon)^2.  S321 measures the positive excess of C2
over that iid benchmark in robustly standardized, non-overlapping baseline and
recent return samples.  A rising excess indicates nonlinear serial structure
that ordinary autocorrelation can miss.

The current closed candle must release with the recent path direction and
break local structure.  Entry is next-open market, the stop is structural plus
ATR, and TP is at least 7R.
"""

from __future__ import annotations

import math
from statistics import median

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 64,
    "RECENT_RETURNS": 32,
    "BDS_EPSILON_MAD": 0.75,
    "RECENT_BDS_EXCESS_MIN": 0.030,
    "BDS_EXCESS_JUMP_MIN": 0.015,
    "PATH_EFFICIENCY_MIN": 0.28,
    "NET_MOVE_ATR_MIN": 0.65,
    "BREAKOUT_LOOKBACK": 10,
    "BREAKOUT_BUFFER_ATR": 0.01,
    "RELEASE_BODY_ATR_MIN": 0.58,
    "RELEASE_RANGE_ATR_MIN": 0.78,
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


def _bds_excess(values, epsilon_mad):
    if len(values) < 12:
        return None
    center = median(values)
    mad = median(abs(value - center) for value in values)
    if mad <= 0.0:
        return None
    standardized = [(value - center) / mad for value in values]
    epsilon = epsilon_mad

    scalar_pairs = scalar_close = 0
    for left in range(len(standardized) - 1):
        for right in range(left + 1, len(standardized)):
            scalar_pairs += 1
            if abs(standardized[left] - standardized[right]) < epsilon:
                scalar_close += 1
    if scalar_pairs <= 0:
        return None
    c1 = scalar_close / scalar_pairs

    vectors = list(zip(standardized[:-1], standardized[1:]))
    vector_pairs = vector_close = 0
    for left in range(len(vectors) - 1):
        for right in range(left + 1, len(vectors)):
            vector_pairs += 1
            if (
                abs(vectors[left][0] - vectors[right][0]) < epsilon
                and abs(vectors[left][1] - vectors[right][1]) < epsilon
            ):
                vector_close += 1
    if vector_pairs <= 0:
        return None
    c2 = vector_close / vector_pairs
    return c2 - c1 * c1


def detect_s321(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a structural release after nonlinear dependence strengthens."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_RETURNS"]))
        recent_count = max(12, int(c["RECENT_RETURNS"]))
        epsilon = float(c["BDS_EPSILON_MAD"])
        recent_min = float(c["RECENT_BDS_EXCESS_MIN"])
        jump_min = float(c["BDS_EXCESS_JUMP_MIN"])
        breakout_lookback = max(3, int(c["BREAKOUT_LOOKBACK"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (epsilon, recent_min, jump_min)
    ):
        return _wait("Invalid config: BDS thresholds must be finite")

    total_returns = baseline_count + recent_count
    required = max(total_returns + 4, period + breakout_lookback + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside liquid session")
    try:
        bars = _bars(rates)
        event = bars[-1]
        closes = [
            bar["close"] for bar in bars[-total_returns - 2:-1]
        ]
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
        baseline = returns[:baseline_count]
        recent = returns[baseline_count:]
        baseline_excess = _bds_excess(baseline, epsilon)
        recent_excess = _bds_excess(recent, epsilon)
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
    if baseline_excess is None or recent_excess is None:
        return _wait("BDS correlation integral is unavailable")
    excess_jump = recent_excess - baseline_excess
    if recent_excess < recent_min or excess_jump < jump_min:
        return _wait(
            f"No nonlinear-dependence shift ({recent_excess:.4f}, "
            f"jump={excess_jump:.4f})"
        )

    recent_bars = bars[-recent_count - 1:-1]
    net_move = recent_bars[-1]["close"] - recent_bars[0]["close"]
    travelled = sum(
        abs(recent_bars[index]["close"] - recent_bars[index - 1]["close"])
        for index in range(1, len(recent_bars))
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
        return _wait("Release opposes the nonlinear path")
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
        "pattern": f"S321 {signal} BDS Dependence Release {rr:g}R",
        "reason": (
            f"BDS excess {baseline_excess:.5f}->{recent_excess:.5f}, "
            f"efficiency={efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
