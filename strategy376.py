# -*- coding: utf-8 -*-
"""S376 — Lagged Signed-Volume Return Forecast.

The detector estimates the closed-bar correlation between signed tick-volume
participation at bar t and close-to-close return at t+1.  Recent absolute
lead correlation must expand versus disjoint baseline blocks.  A high-volume
event then supplies the signed predictor for the next bar.  The deployed
configuration follows positive persistence only; the reversal branch remains
available as an explicit research toggle because it failed every validation
window.

No future bar is inspected.  The market signal is filled by the caller at the
next bar open.
"""

from __future__ import annotations

import math
import statistics


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 60,
    "RECENT_BARS": 24,
    "LEAD_CORRELATION_MIN": 0.20,
    "LEAD_CORRELATION_RATIO_MIN": 1.40,
    "EVENT_VOLUME_RATIO_MIN": 1.10,
    "EVENT_BODY_ATR_MIN": 0.25,
    "EVENT_RANGE_ATR_MIN": 0.60,
    "EVENT_BODY_FRACTION_MIN": 0.45,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_PERSISTENCE": True,
    "ALLOW_REVERSAL": False,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 9.0,
    "BE_RR": 0.01,
    "CANCEL_BARS": 3,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite rate value")
    return number


def _bars(rates):
    result = []
    previous_time = None
    for raw in rates:
        timestamp = int(_finite(raw["time"]))
        if previous_time is not None and timestamp <= previous_time:
            raise ValueError("rates must be chronological")
        previous_time = timestamp
        bar = {
            "time": timestamp,
            "open": _finite(raw["open"]),
            "high": _finite(raw["high"]),
            "low": _finite(raw["low"]),
            "close": _finite(raw["close"]),
            "tick_volume": max(1.0, _finite(raw["tick_volume"])),
        }
        if bar["high"] < max(bar["open"], bar["close"], bar["low"]):
            raise ValueError("invalid high")
        if bar["low"] > min(bar["open"], bar["close"], bar["high"]):
            raise ValueError("invalid low")
        if min(bar["open"], bar["high"], bar["low"], bar["close"]) <= 0.0:
            raise ValueError("prices must be positive")
        result.append(bar)
    return result


def _atr(bars, period):
    if period < 1 or len(bars) < period + 1:
        return 0.0
    values = []
    for index in range(len(bars) - period, len(bars)):
        bar = bars[index]
        previous_close = bars[index - 1]["close"]
        values.append(max(
            bar["high"] - bar["low"],
            abs(bar["high"] - previous_close),
            abs(bar["low"] - previous_close),
        ))
    return sum(values) / len(values)


def _pearson(left, right):
    if len(left) != len(right) or len(left) < 6:
        return None
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    left_delta = [value - left_mean for value in left]
    right_delta = [value - right_mean for value in right]
    left_energy = sum(value * value for value in left_delta)
    right_energy = sum(value * value for value in right_delta)
    if left_energy <= 0.0 or right_energy <= 0.0:
        return None
    covariance = sum(
        a * b for a, b in zip(left_delta, right_delta)
    )
    return covariance / math.sqrt(left_energy * right_energy)


def _lead_profile(bars):
    if len(bars) < 9:
        return None
    median_volume = statistics.median(
        bar["tick_volume"] for bar in bars[:-1]
    )
    if median_volume <= 0.0:
        return None
    predictors = []
    targets = []
    for index in range(1, len(bars) - 1):
        bar = bars[index]
        body = bar["close"] - bar["open"]
        if body == 0.0:
            predictor = 0.0
        else:
            predictor = (
                (1.0 if body > 0.0 else -1.0)
                * bar["tick_volume"]
                / median_volume
            )
        predictors.append(predictor)
        targets.append(math.log(
            bars[index + 1]["close"] / bar["close"]
        ))
    correlation = _pearson(predictors, targets)
    if correlation is None or not math.isfinite(correlation):
        return None
    return correlation, median_volume


def detect_s376(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S376 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(9, int(c["RECENT_BARS"]))
        correlation_min = float(c["LEAD_CORRELATION_MIN"])
        correlation_ratio_min = float(c["LEAD_CORRELATION_RATIO_MIN"])
        event_volume_min = float(c["EVENT_VOLUME_RATIO_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (
            correlation_min,
            correlation_ratio_min,
            event_volume_min,
        )
    ):
        return _wait("Invalid config: lead-lag gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates[-required:])
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        baseline_correlations = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _lead_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_correlations.append(abs(profile[0]))
        recent_profile = _lead_profile(recent)
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
    if recent_profile is None or not baseline_correlations:
        return _wait("Signed-volume lead profile is unavailable")

    correlation, recent_volume = recent_profile
    baseline_correlation = statistics.median(baseline_correlations)
    if baseline_correlation <= 0.0 or recent_volume <= 0.0:
        return _wait("Baseline lead profile is zero")
    correlation_ratio = abs(correlation) / baseline_correlation
    if abs(correlation) < correlation_min:
        return _wait(f"Lead correlation is weak ({correlation:.3f})")
    if correlation_ratio < correlation_ratio_min:
        return _wait(f"No lead-correlation expansion ({correlation_ratio:.3f}x)")

    body = float(event["close"]) - float(event["open"])
    candle_range = float(event["high"]) - float(event["low"])
    event_volume_ratio = float(event["tick_volume"]) / recent_volume
    if body == 0.0 or candle_range <= 0.0:
        return _wait("Event impulse is flat")
    if event_volume_ratio < event_volume_min:
        return _wait(f"Event volume surprise is weak ({event_volume_ratio:.3f}x)")
    if abs(body) < atr * float(c["EVENT_BODY_ATR_MIN"]):
        return _wait("Event body is too small versus ATR")
    if candle_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Event range is too small versus ATR")
    if abs(body) / candle_range < float(c["EVENT_BODY_FRACTION_MIN"]):
        return _wait("Event impulse lacks body control")

    event_side = 1 if body > 0.0 else -1
    correlation_side = 1 if correlation > 0.0 else -1
    mode = "persistence" if correlation > 0.0 else "reversal"
    if mode == "persistence" and not bool(c["ALLOW_PERSISTENCE"]):
        return _wait("Persistence mode disabled")
    if mode == "reversal" and not bool(c["ALLOW_REVERSAL"]):
        return _wait("Reversal mode disabled")
    side = event_side * correlation_side
    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(float(event["close"]), 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor(
            (float(event["low"]) - sl_buffer + 1e-12) * 100.0
        ) / 100.0
    else:
        sl = math.ceil(
            (float(event["high"]) + sl_buffer - 1e-12) * 100.0
        ) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Event risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Event risk too large versus price")

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
        "pattern": f"S376 {signal} Volume Lead {rr:g}R",
        "reason": (
            f"{mode} corr={correlation:.4f}, "
            f"expansion={correlation_ratio:.4f}x, "
            f"event volume={event_volume_ratio:.4f}x"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
