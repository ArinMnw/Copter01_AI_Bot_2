# -*- coding: utf-8 -*-
"""S349 - Jensen-Shannon quantile-occupancy tilt release.

S349 measures the information shift between baseline and recent closed-return
histograms with normalized Jensen-Shannon divergence.  Direction comes from
probability mass moving toward the upper or lower baseline quantile bins,
rather than the median/MAD displacement used by S346.

All distribution and path inputs precede the release candle.  Entry is
next-open market, SL is beyond the closed release extreme plus ATR, and TP is
at least 7R.
"""

from __future__ import annotations

import bisect
import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy346 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 64,
    "RECENT_RETURNS": 20,
    "HISTOGRAM_BINS": 6,
    "JS_DIVERGENCE_MIN": 0.12,
    "JS_EXCESS_MIN": 0.03,
    "RECENT_MASS_TILT_MIN": 0.35,
    "MASS_TILT_SHIFT_MIN": 0.12,
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
    "ALLOW_SELL": False,
    "TP_RR": 8.0,
    "BE_RR": 0.05,
    "CANCEL_BARS": 3,
}


def _js_profile(reference, sample, bin_count):
    if len(reference) < bin_count * 2 or len(sample) < bin_count:
        return None
    ordered = sorted(reference)
    cuts = [
        _quantile(ordered, index / bin_count)
        for index in range(1, bin_count)
    ]
    reference_counts = [0] * bin_count
    sample_counts = [0] * bin_count
    for value in reference:
        reference_counts[bisect.bisect_right(cuts, value)] += 1
    for value in sample:
        sample_counts[bisect.bisect_right(cuts, value)] += 1
    p = [count / len(reference) for count in reference_counts]
    q = [count / len(sample) for count in sample_counts]
    divergence = 0.0
    for probability_p, probability_q in zip(p, q):
        mixture = 0.5 * (probability_p + probability_q)
        if probability_p > 0.0:
            divergence += 0.5 * probability_p * math.log(
                probability_p / mixture
            )
        if probability_q > 0.0:
            divergence += 0.5 * probability_q * math.log(
                probability_q / mixture
            )
    divergence /= math.log(2.0)
    return divergence, p, q


def _outer_mass_tilt(probabilities):
    if len(probabilities) < 4:
        raise ValueError("too few probabilities for outer-mass tilt")
    return (
        probabilities[-1]
        + probabilities[-2]
        - probabilities[0]
        - probabilities[1]
    )


def detect_s349(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a directional Jensen-Shannon occupancy shift."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_RETURNS"]))
        recent_count = max(8, int(c["RECENT_RETURNS"]))
        bin_count = max(4, int(c["HISTOGRAM_BINS"]))
        divergence_min = float(c["JS_DIVERGENCE_MIN"])
        excess_min = float(c["JS_EXCESS_MIN"])
        tilt_min = float(c["RECENT_MASS_TILT_MIN"])
        tilt_shift_min = float(c["MASS_TILT_SHIFT_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count // 2 < bin_count * 2:
        return _wait("Invalid config: baseline too short for histogram bins")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (
            divergence_min,
            excess_min,
            tilt_min,
            tilt_shift_min,
        )
    ):
        return _wait("Invalid config: Jensen-Shannon gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 2)
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
        drift_profile = _js_profile(
            baseline[:split],
            baseline[split:],
            bin_count,
        )
        shift_profile = _js_profile(baseline, recent, bin_count)
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
    if drift_profile is None or shift_profile is None:
        return _wait("Jensen-Shannon profile is unavailable")

    drift = drift_profile[0]
    divergence, baseline_probabilities, recent_probabilities = shift_profile
    excess = divergence - drift
    baseline_tilt = _outer_mass_tilt(baseline_probabilities)
    recent_tilt = _outer_mass_tilt(recent_probabilities)
    side = 1 if recent_tilt > 0.0 else -1
    directional_tilt_shift = side * (recent_tilt - baseline_tilt)
    if (
        divergence < divergence_min
        or excess < excess_min
        or abs(recent_tilt) < tilt_min
        or directional_tilt_shift < tilt_shift_min
    ):
        return _wait(
            f"No directional Jensen-Shannon shift "
            f"(JS={divergence:.3f}, drift={drift:.3f}, "
            f"excess={excess:.3f}, tilt={recent_tilt:.3f}, "
            f"tilt_shift={directional_tilt_shift:.3f})"
        )

    recent_bars = history[-recent_count - 1:]
    net_move = recent_bars[-1]["close"] - recent_bars[0]["close"]
    travelled = sum(
        abs(
            recent_bars[index]["close"]
            - recent_bars[index - 1]["close"]
        )
        for index in range(1, len(recent_bars))
    )
    if travelled <= 0.0 or net_move * side <= 0.0:
        return _wait("Recent path opposes occupancy-tilt direction")
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes occupancy-tilt direction")
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
        "pattern": f"S349 {signal} JS Occupancy Tilt {rr:g}R",
        "reason": (
            f"JS={divergence:.4f}, drift={drift:.4f}, "
            f"excess={excess:.4f}, mass tilt={recent_tilt:.4f}, "
            f"tilt shift={directional_tilt_shift:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
