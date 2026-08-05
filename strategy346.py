# -*- coding: utf-8 -*-
"""S346 - Hellinger return-distribution shift release.

S346 compares recent closed returns with a baseline using a discrete
quantile-bin Hellinger distance.  The shift must exceed the baseline's own
two-half drift and have a material median displacement before a directional
release is followed.

All distribution and path inputs precede the release candle.  Entry is
next-open market, SL is beyond the closed release extreme plus ATR, and TP is
at least 7R.
"""

from __future__ import annotations

import bisect
import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 64,
    "RECENT_RETURNS": 20,
    "HISTOGRAM_BINS": 6,
    "HELLINGER_MIN": 0.30,
    "HELLINGER_EXCESS_MIN": 0.10,
    "MEDIAN_SHIFT_MAD_MIN": 0.70,
    "PATH_EFFICIENCY_MIN": 0.22,
    "NET_MOVE_ATR_MIN": 0.55,
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
    "TP_RR": 11.0,
    "BE_RR": 0.08,
    "CANCEL_BARS": 3,
}


def _quantile(sorted_values, probability):
    if not sorted_values:
        raise ValueError("empty quantile sample")
    position = (len(sorted_values) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return (
        sorted_values[lower] * (1.0 - fraction)
        + sorted_values[upper] * fraction
    )


def _hellinger(reference, sample, bin_count):
    if len(reference) < bin_count * 2 or len(sample) < bin_count:
        return None
    ordered = sorted(reference)
    cuts = [
        _quantile(ordered, index / bin_count)
        for index in range(1, bin_count)
    ]
    ref_counts = [0] * bin_count
    sample_counts = [0] * bin_count
    for value in reference:
        ref_counts[bisect.bisect_right(cuts, value)] += 1
    for value in sample:
        sample_counts[bisect.bisect_right(cuts, value)] += 1
    squared = 0.0
    for ref_count, sample_count in zip(ref_counts, sample_counts):
        ref_probability = ref_count / len(reference)
        sample_probability = sample_count / len(sample)
        squared += (
            math.sqrt(ref_probability) - math.sqrt(sample_probability)
        ) ** 2
    return math.sqrt(0.5 * squared)


def detect_s346(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a directional Hellinger distribution shift."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_RETURNS"]))
        recent_count = max(8, int(c["RECENT_RETURNS"]))
        bin_count = max(3, int(c["HISTOGRAM_BINS"]))
        hellinger_min = float(c["HELLINGER_MIN"])
        excess_min = float(c["HELLINGER_EXCESS_MIN"])
        median_shift_min = float(c["MEDIAN_SHIFT_MAD_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count // 2 < bin_count * 2:
        return _wait("Invalid config: baseline too short for histogram bins")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (hellinger_min, excess_min, median_shift_min)
    ):
        return _wait("Invalid config: Hellinger gates are invalid")

    required = max(
        period + 5,
        baseline_count + recent_count + 2,
    )
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 2:-1]
        returns = [
            history[index]["close"] - history[index - 1]["close"]
            for index in range(1, len(history))
        ]
        baseline = returns[:baseline_count]
        recent = returns[baseline_count:]
        split = baseline_count // 2
        drift = _hellinger(
            baseline[:split],
            baseline[split:],
            bin_count,
        )
        shift = _hellinger(baseline, recent, bin_count)
        baseline_median = statistics.median(baseline)
        recent_median = statistics.median(recent)
        baseline_mad = statistics.median(
            abs(value - baseline_median) for value in baseline
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
    if atr <= 0.0:
        return _wait("ATR is zero")
    if drift is None or shift is None or baseline_mad <= 1e-12:
        return _wait("Hellinger distribution profile is unavailable")

    excess = shift - drift
    median_shift_mad = (recent_median - baseline_median) / baseline_mad
    if (
        shift < hellinger_min
        or excess < excess_min
        or abs(median_shift_mad) < median_shift_min
    ):
        return _wait(
            f"No material Hellinger shift "
            f"(H={shift:.3f}, drift={drift:.3f}, excess={excess:.3f}, "
            f"median/MAD={median_shift_mad:.3f})"
        )

    side = 1 if median_shift_mad > 0.0 else -1
    recent_bars = history[-recent_count - 1:]
    net_move = recent_bars[-1]["close"] - recent_bars[0]["close"]
    travelled = sum(
        abs(recent_bars[index]["close"] - recent_bars[index - 1]["close"])
        for index in range(1, len(recent_bars))
    )
    if travelled <= 0.0 or net_move * side <= 0.0:
        return _wait("Recent path opposes distribution-shift direction")
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes distribution-shift direction")
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
        "pattern": f"S346 {signal} Hellinger Shift {rr:g}R",
        "reason": (
            f"Hellinger={shift:.4f}, drift={drift:.4f}, "
            f"excess={excess:.4f}, median/MAD={median_shift_mad:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
