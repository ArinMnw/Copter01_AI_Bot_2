# -*- coding: utf-8 -*-
"""S290 - Wasserstein return-distribution drift resumption, 25.4R.

The detector compares baseline and recent empirical return distributions with
a normalized first Wasserstein distance.  A signed median shift supplies the
direction, while a strong closed candle must resume that drift.  This measures
whole-distribution migration rather than the scale-only Mood regimes in
S288/S289 or the price-level change point used by S287.
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
    "BASELINE_WINDOW": 48,
    "RECENT_WINDOW": 16,
    "WASSERSTEIN_MAD_MIN": 0.625,
    "MEDIAN_SHIFT_MAD_MIN": 0.8375,
    "RELEASE_BODY_ATR_MIN": 0.55,
    "RELEASE_RANGE_ATR_MIN": 0.75,
    "RELEASE_CLOSE_FRACTION": 0.62,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 25.40,
    "BE_RR": 1.475,
    "CANCEL_BARS": 3,
}


def _wasserstein_drift(baseline, recent):
    """Return normalized W1 distance and signed median shift."""
    if len(baseline) < 8 or len(recent) < 4:
        return None
    base_sorted = sorted(float(value) for value in baseline)
    recent_sorted = sorted(float(value) for value in recent)
    if any(not math.isfinite(value) for value in base_sorted + recent_sorted):
        return None
    base_median = median(base_sorted)
    recent_median = median(recent_sorted)
    base_mad = median(abs(value - base_median) for value in base_sorted)
    if base_mad <= 0.0:
        return None
    # Exact one-dimensional W1 = integral |F_baseline(x) - F_recent(x)| dx.
    support = sorted(set(base_sorted + recent_sorted))
    base_index = 0
    recent_index = 0
    distance = 0.0
    for index in range(len(support) - 1):
        value = support[index]
        while (
            base_index < len(base_sorted)
            and base_sorted[base_index] <= value
        ):
            base_index += 1
        while (
            recent_index < len(recent_sorted)
            and recent_sorted[recent_index] <= value
        ):
            recent_index += 1
        width = support[index + 1] - value
        distance += abs(
            base_index / len(base_sorted)
            - recent_index / len(recent_sorted)
        ) * width
    normalized_w1 = distance / base_mad
    normalized_shift = (recent_median - base_median) / base_mad
    return normalized_w1, normalized_shift


def detect_s290(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a controlled release aligned with robust return-distribution drift."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_window = max(8, int(c["BASELINE_WINDOW"]))
        recent_window = max(4, int(c["RECENT_WINDOW"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    history_returns = baseline_window + recent_window
    required = max(history_returns + 4, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [bar["close"] for bar in bars[-history_returns - 2:-1]]
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
        drift = _wasserstein_drift(
            returns[:baseline_window],
            returns[baseline_window:],
        )
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
    if drift is None:
        return _wait("Return-distribution drift is unavailable")
    normalized_w1, normalized_shift = drift
    if normalized_w1 < float(c["WASSERSTEIN_MAD_MIN"]):
        return _wait(f"Distribution drift is too small ({normalized_w1:.2f} MAD)")
    shift_floor = float(c["MEDIAN_SHIFT_MAD_MIN"])
    if abs(normalized_shift) < shift_floor:
        return _wait(f"Median drift is too small ({normalized_shift:.2f} MAD)")
    drift_side = 1 if normalized_shift > 0.0 else -1

    event = bars[-1]
    event_body = event["close"] - event["open"]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Release candle has zero range")
    if abs(event_body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if event_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    if event_body * drift_side <= 0.0:
        return _wait("Release candle opposes the return-distribution drift")
    if drift_side > 0:
        signal, side = "BUY", 1
        close_location = (event["close"] - event["low"]) / event_range
    else:
        signal, side = "SELL", -1
        close_location = (event["high"] - event["close"]) / event_range
    if close_location < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Release candle closes without directional control")
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
        "pattern": f"S290 {signal} Wasserstein Drift {rr:g}R",
        "reason": (
            f"Return distribution drifted {normalized_w1:.2f} MAD with "
            f"signed median shift {normalized_shift:+.2f} MAD"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
