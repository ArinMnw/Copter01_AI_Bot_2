# -*- coding: utf-8 -*-
"""S311 - Cramer-von Mises distribution-shift release, optimized SELL 10.1R.

This opens a new branch after the rollover experiments.  S301's two-sample KS
gate measures the single largest empirical-CDF separation; S300 emphasizes the
tails; S290 integrates transport distance in return units.  S311 instead uses
the distribution-free two-sample Cramer-von Mises statistic, integrating squared
ECDF separation over every pooled rank.  It should detect broad reshaping that
is neither a one-quantile jump nor a tail-only anomaly.

Non-overlapping baseline/recent log returns define the causal distribution
change.  A MAD-normalized median shift supplies direction and a closed release
candle confirms that the new distribution is expressed in price.  Stop
placement is structural plus ATR buffer and the target is at least 7R.
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
    # Optional tuple for stability research.  Empty keeps the single-window
    # optimized detector; non-empty values aggregate CvM/shift by median and
    # require every window to agree on direction.
    "RECENT_RETURNS_ENSEMBLE": (),
    # 0.275-0.300 is the cross-window plateau; 0.400 loses every TP.
    "CVM_MIN": 0.2875,
    # 0.20-0.25 is an identical cross-window plateau.  The weakest retained
    # long-window TP is 0.310MAD, so use the midpoint with useful headroom.
    "MEDIAN_SHIFT_MAD_MIN": 0.225,
    "RELEASE_BODY_ATR_MIN": 0.575,
    # Shape sweep: 1.00 is a cross-window Pareto improvement over 0.8375,
    # removing five noise trades without losing a TP.
    "RELEASE_RANGE_ATR_MIN": 1.00,
    "RELEASE_CLOSE_FRACTION": 0.8325,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    # SELL survives 2m/6m/WF with materially lower drawdown.  BUY remains
    # available for ablation but is disabled in the optimized default.
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    # The recent TP survives through 10.3R and disappears at 10.4R.  Keep a
    # 0.2R safety margin.  BE 0.20-0.30 is the shared low-DD plateau.
    "TP_RR": 10.1,
    "BE_RR": 0.25,
    "CANCEL_BARS": 3,
}


def _cvm_distribution_shift(baseline, recent):
    """Return the tie-aware two-sample CvM statistic and robust signed shift."""
    n1, n2 = len(baseline), len(recent)
    if n1 < 8 or n2 < 4:
        return None
    try:
        first = sorted(float(value) for value in baseline)
        second = sorted(float(value) for value in recent)
    except (TypeError, ValueError, OverflowError):
        return None
    if any(not math.isfinite(value) for value in first + second):
        return None

    support = sorted(set(first + second))
    i = j = previous_i = previous_j = 0
    squared_area = 0.0
    for value in support:
        while i < n1 and first[i] <= value:
            i += 1
        while j < n2 and second[j] <= value:
            j += 1
        multiplicity = (i - previous_i) + (j - previous_j)
        squared_area += multiplicity * (i / n1 - j / n2) ** 2
        previous_i, previous_j = i, j
    total = n1 + n2
    statistic = (n1 * n2 / (total * total)) * squared_area

    pooled = first + second
    pooled_median = median(pooled)
    mad = median(abs(value - pooled_median) for value in pooled)
    if mad <= 0.0:
        return None
    shift = (median(second) - median(first)) / mad
    return statistic, shift


def detect_s311(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a confirmed broad empirical-distribution shift."""
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
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
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
            measured = _cvm_distribution_shift(baseline, recent)
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
        return _wait("Cramer-von Mises distribution shift is unavailable")
    directions = {1 if robust_shift > 0.0 else -1 for _, robust_shift in shifts}
    if len(directions) != 1:
        return _wait("CvM windows disagree on robust direction")
    cvm = median(value for value, _ in shifts)
    median_shift = median(value for _, value in shifts)
    if cvm < float(c["CVM_MIN"]):
        return _wait(f"Empirical distributions remain too similar (CvM={cvm:.3f})")
    if abs(median_shift) < float(c["MEDIAN_SHIFT_MAD_MIN"]):
        return _wait(
            f"Distribution shift lacks robust direction ({median_shift:.3f}MAD)"
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
        "pattern": f"S311 {signal} CvM Distribution Shift {rr:g}R",
        "reason": (
            f"Broad ECDF shift CvM={cvm:.6f}, "
            f"median shift={median_shift:.6f}MAD"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
