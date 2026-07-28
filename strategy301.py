# -*- coding: utf-8 -*-
"""S301 - two-sample Kolmogorov-Smirnov distribution-break, SELL 10.2R.

S301 compares non-overlapping baseline and recent closed log returns with the
exact empirical two-sample KS distance.  The scaled maximum CDF separation
detects a localized distribution break that can be diluted by an integrated
distance such as S290's Wasserstein statistic.  A robust signed median shift
sets direction, and a closed release candle must confirm the new regime.
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
    "KS_SCALED_MIN": 1.05,
    "MEDIAN_SHIFT_MAD_MIN": 0.125,
    "RELEASE_BODY_ATR_MIN": 0.575,
    "RELEASE_RANGE_ATR_MIN": 0.8375,
    "RELEASE_CLOSE_FRACTION": 0.8325,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    "TP_RR": 10.2,
    "BE_RR": 0.25,
    "CANCEL_BARS": 3,
}


def _ks_distribution_shift(baseline, recent):
    """Return scaled exact two-sample KS distance and MAD-normalized shift."""
    n1, n2 = len(baseline), len(recent)
    if n1 < 8 or n2 < 4:
        return None
    try:
        first = [float(value) for value in baseline]
        second = [float(value) for value in recent]
    except (TypeError, ValueError, OverflowError):
        return None
    if any(not math.isfinite(value) for value in first + second):
        return None

    ordered_first = sorted(first)
    ordered_second = sorted(second)
    support = sorted(set(ordered_first + ordered_second))
    i = j = 0
    distance = 0.0
    for value in support:
        while i < n1 and ordered_first[i] <= value:
            i += 1
        while j < n2 and ordered_second[j] <= value:
            j += 1
        distance = max(distance, abs(i / n1 - j / n2))
    scaled_distance = math.sqrt(n1 * n2 / (n1 + n2)) * distance

    pooled = first + second
    pooled_median = median(pooled)
    mad = median(abs(value - pooled_median) for value in pooled)
    if mad <= 0.0:
        return None
    shift = (median(second) - median(first)) / mad
    return scaled_distance, shift


def detect_s301(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a closed release after a localized empirical-CDF regime break."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(8, int(c["BASELINE_RETURNS"]))
        recent_count = max(4, int(c["RECENT_RETURNS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    total_returns = baseline_count + recent_count
    required = max(total_returns + 4, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [
            bar["close"] for bar in bars[-total_returns - 2:-1]
        ]
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
        baseline = returns[:baseline_count]
        recent = returns[baseline_count:]
        shift = _ks_distribution_shift(baseline, recent)
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
    if shift is None:
        return _wait("KS distribution shift is unavailable")
    ks_scaled, median_shift = shift
    if ks_scaled < float(c["KS_SCALED_MIN"]):
        return _wait(f"Empirical CDFs remain too similar (KSz={ks_scaled:.3f})")
    if abs(median_shift) < float(c["MEDIAN_SHIFT_MAD_MIN"]):
        return _wait(
            f"Distribution break lacks robust direction ({median_shift:.3f}MAD)"
        )

    regime_side = 1 if median_shift > 0.0 else -1
    event = bars[-1]
    event_body = event["close"] - event["open"]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Release candle has zero range")
    if event_body * regime_side <= 0.0:
        return _wait("Release candle opposes the distribution shift")
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
        return _wait("Release candle closes without shifted-regime control")
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled by direction-survival filter")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled by direction-survival filter")

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
        "pattern": f"S301 {signal} KS Distribution Break {rr:g}R",
        "reason": (
            f"Empirical CDF break KSz={ks_scaled:.6f}, "
            f"median shift={median_shift:.6f}MAD"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
