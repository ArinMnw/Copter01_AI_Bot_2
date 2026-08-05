# -*- coding: utf-8 -*-
"""S312 - Energy-distance distribution break release, optimized SELL 10.1R.

S311 measures a two-sample distribution change by integrating squared ECDF
rank separation.  S312 deliberately changes the geometry: energy distance
compares every cross-sample absolute return distance with both within-sample
distances.  After normalization by pooled MAD it can detect location, scale,
and shape changes without binning, a Gaussian assumption, or one selected
quantile.

Only non-overlapping closed log-return samples are used.  A robust median shift
sets direction and the current fully closed candle must release in that
direction with institutional range/body/close geometry.  Execution is market
at the next bar open in the repository backtester.  The stop is beyond the
release extreme plus an ATR buffer and the target is never below 7R.
"""

from __future__ import annotations

import math
from statistics import median

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "BASELINE_RETURNS": 48,
    "RECENT_RETURNS": 16,
    # Optional stability research mode.  Empty preserves the optimized
    # single-window detector; non-empty windows aggregate by median and must
    # all agree on shift direction.
    "RECENT_RETURNS_ENSEMBLE": (),
    # Dimensionless after pooled-MAD normalization.
    # 0.22-0.235 retains every cross-window SELL winner.  Use the midpoint
    # with margin below the weakest retained winner at 0.235574.
    "ENERGY_MIN": 0.225,
    "MEDIAN_SHIFT_MAD_MIN": 0.225,
    # Shape plateau: body 0.775-0.80 and range 0.70-0.90 preserve the same
    # winner set with low drawdown.  Midpoints avoid selecting a boundary.
    "RELEASE_BODY_ATR_MIN": 0.7875,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.8325,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    # BUY loses money in the latest six-month audit; SELL is positive in
    # recent, H1, and the non-overlapping walk-forward half-year.
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    # TP is stable through 10.35R and fails cross-window at 10.40R.  Keep a
    # 0.30R margin.  BE 0.05-0.10 is an identical cross-window plateau.
    "TP_RR": 10.1,
    "BE_RR": 0.075,
    "CANCEL_BARS": 3,
}


def _mean_pair_distance(first, second):
    if not first or not second:
        return None
    return sum(abs(left - right) for left in first for right in second) / (
        len(first) * len(second)
    )


def _energy_distribution_shift(baseline, recent):
    """Return dimensionless biased energy distance and robust signed shift."""
    if len(baseline) < 8 or len(recent) < 4:
        return None
    try:
        first = [float(value) for value in baseline]
        second = [float(value) for value in recent]
    except (TypeError, ValueError, OverflowError):
        return None
    pooled = first + second
    if any(not math.isfinite(value) for value in pooled):
        return None
    pooled_median = median(pooled)
    mad = median(abs(value - pooled_median) for value in pooled)
    if mad <= 0.0:
        return None
    first_scaled = [(value - pooled_median) / mad for value in first]
    second_scaled = [(value - pooled_median) / mad for value in second]
    cross = _mean_pair_distance(first_scaled, second_scaled)
    within_first = _mean_pair_distance(first_scaled, first_scaled)
    within_second = _mean_pair_distance(second_scaled, second_scaled)
    if cross is None or within_first is None or within_second is None:
        return None
    distance = max(0.0, 2.0 * cross - within_first - within_second)
    shift = (median(second) - median(first)) / mad
    return distance, shift


def detect_s312(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a closed-candle release after a full-distribution energy break."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(8, int(c["BASELINE_RETURNS"]))
        recent_count = max(4, int(c["RECENT_RETURNS"]))
        raw_ensemble = tuple(c.get("RECENT_RETURNS_ENSEMBLE", ()) or ())
        recent_windows = (
            tuple(max(4, int(value)) for value in raw_ensemble)
            if raw_ensemble
            else (recent_count,)
        )
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
        energy_min = float(c["ENERGY_MIN"])
        shift_min = float(c["MEDIAN_SHIFT_MAD_MIN"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not math.isfinite(energy_min) or energy_min < 0.0:
        return _wait("Invalid config: ENERGY_MIN must be finite and non-negative")
    if not math.isfinite(shift_min) or shift_min < 0.0:
        return _wait(
            "Invalid config: MEDIAN_SHIFT_MAD_MIN must be finite and non-negative"
        )

    total_returns = baseline_count + max(recent_windows)
    required = max(total_returns + 4, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [bar["close"] for bar in bars[-total_returns - 2:-1]]
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
        shifts = []
        for window_count in recent_windows:
            segment = returns[-(baseline_count + window_count):]
            baseline = segment[:baseline_count]
            recent = segment[baseline_count:]
            measured = _energy_distribution_shift(baseline, recent)
            if measured is None:
                shifts = []
                break
            shifts.append(measured)
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
    if not shifts:
        return _wait("Energy distribution shift is unavailable")
    directions = {1 if robust_shift > 0.0 else -1 for _, robust_shift in shifts}
    if len(directions) != 1:
        return _wait("Energy windows disagree on robust direction")
    energy = median(value for value, _ in shifts)
    median_shift = median(value for _, value in shifts)
    if energy < energy_min:
        return _wait(f"Distributions remain too similar (energy={energy:.3f})")
    if abs(median_shift) < shift_min:
        return _wait(
            f"Energy break lacks robust direction ({median_shift:.3f}MAD)"
        )

    regime_side = 1 if median_shift > 0.0 else -1
    event = bars[-1]
    event_body = event["close"] - event["open"]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Release candle has zero range")
    if event_body * regime_side <= 0.0:
        return _wait("Release candle opposes the energy break")
    if abs(event_body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if event_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    if regime_side > 0:
        signal, side = "BUY", 1
        close_location = (event["close"] - event["low"]) / event_range
    else:
        signal, side = "SELL", -1
        close_location = (event["high"] - event["close"]) / event_range
    if close_location < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Release candle lacks directional close control")
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")

    entry = round(event["close"], 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor((event["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Release risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Release risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    if side > 0:
        tp = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
    else:
        tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S312 {signal} Energy Distribution Break {rr:g}R",
        "reason": (
            f"Energy distance={energy:.6f}, "
            f"median shift={median_shift:.6f}MAD"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
