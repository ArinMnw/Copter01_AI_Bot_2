# -*- coding: utf-8 -*-
"""S316 - Permutation-entropy compression release.

Permutation entropy summarizes the full distribution of ordinal return
patterns.  A drop from a high-entropy baseline to an organized recent path
indicates that noisy price discovery has compressed into a directional state.
The detector follows only a closed structural release in that state.

This differs from S263's posterior for one ordinal pattern and from Lempel-Ziv
phrase complexity: S316 measures normalized Shannon entropy across all order-3
permutations in two non-overlapping samples.  Execution is next-open market,
with a release-extreme ATR stop and TP of at least 7R.
"""

from __future__ import annotations

import math
from collections import Counter

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 54,
    "RECENT_RETURNS": 18,
    "PATTERN_ORDER": 3,
    "BASELINE_ENTROPY_MIN": 0.88,
    "RECENT_ENTROPY_MAX": 0.90,
    "ENTROPY_DROP_MIN": 0.04,
    "PATH_EFFICIENCY_MIN": 0.30,
    "NET_MOVE_ATR_MIN": 0.60,
    "BREAKOUT_LOOKBACK": 10,
    "BREAKOUT_BUFFER_ATR": 0.01,
    "RELEASE_BODY_ATR_MIN": 0.55,
    "RELEASE_RANGE_ATR_MIN": 0.75,
    "RELEASE_CLOSE_FRACTION": 0.78,
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


def _ordinal_pattern(values):
    # Index is the deterministic tie-breaker, avoiding unstable equal ranks.
    return tuple(
        index for index, _ in sorted(
            enumerate(values), key=lambda item: (item[1], item[0])
        )
    )


def _permutation_entropy(values, order):
    if len(values) < order + 2:
        return None
    counts = Counter(
        _ordinal_pattern(values[index:index + order])
        for index in range(len(values) - order + 1)
    )
    total = float(sum(counts.values()))
    if total <= 0.0:
        return None
    entropy = -sum(
        (count / total) * math.log(count / total)
        for count in counts.values()
    )
    maximum = math.log(math.factorial(order))
    return entropy / maximum if maximum > 0.0 else None


def detect_s316(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a structural release after ordinal-entropy compression."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(12, int(c["BASELINE_RETURNS"]))
        recent_count = max(8, int(c["RECENT_RETURNS"]))
        order = int(c["PATTERN_ORDER"])
        breakout_lookback = max(3, int(c["BREAKOUT_LOOKBACK"]))
        baseline_min = float(c["BASELINE_ENTROPY_MIN"])
        recent_max = float(c["RECENT_ENTROPY_MAX"])
        drop_min = float(c["ENTROPY_DROP_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if order < 2 or order > 5:
        return _wait("Invalid config: PATTERN_ORDER must be 2..5")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (baseline_min, recent_max, drop_min)
    ):
        return _wait("Invalid config: entropy thresholds must be in [0, 1]")

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
        baseline_entropy = _permutation_entropy(baseline, order)
        recent_entropy = _permutation_entropy(recent, order)
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
    if baseline_entropy is None or recent_entropy is None:
        return _wait("Permutation entropy is unavailable")
    entropy_drop = baseline_entropy - recent_entropy
    if baseline_entropy < baseline_min:
        return _wait(f"Baseline is already ordered ({baseline_entropy:.3f})")
    if recent_entropy > recent_max or entropy_drop < drop_min:
        return _wait(
            f"No entropy compression ({recent_entropy:.3f}, "
            f"drop={entropy_drop:.3f})"
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
        return _wait("Release opposes the ordered path")
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
        "pattern": f"S316 {signal} Permutation Entropy Release {rr:g}R",
        "reason": (
            f"permutation entropy {baseline_entropy:.4f}->"
            f"{recent_entropy:.4f}, efficiency={efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
