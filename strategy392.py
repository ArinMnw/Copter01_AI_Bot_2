# -*- coding: utf-8 -*-
"""S392 — Signed-Flow Information-Gain Release 8R.

Signed tick-volume pressure is discretized into weak/strong buy/sell states.
The strategy measures how much those states reduce uncertainty about the next
bar direction using normalized mutual information.  Recent information gain
must exceed its older baseline, and the current state's Laplace-smoothed next-
bar probability must be decisive.  This nonlinear mapping can express either
continuation or reversal without fitting a linear correlation coefficient.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _quantile, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 80,
    "RECENT_BARS": 28,
    "PRESSURE_QUANTILE": 0.55,
    "LAPLACE_ALPHA": 0.50,
    "INFO_GAIN_MIN": 0.08,
    "INFO_GAIN_RISE_MIN": 0.03,
    "STATE_CONFIDENCE_MIN": 0.75,
    "MIN_STATE_OBSERVATIONS": 4,
    "EVENT_VOLUME_RATIO_MIN": 1.10,
    "EVENT_BODY_ATR_MIN": 0.55,
    "EVENT_RANGE_ATR_MIN": 0.70,
    "EVENT_BODY_FRACTION_MIN": 0.65,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.24,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": False,
    "TP_RR": 8.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _pressure(bar):
    body = bar["close"] - bar["open"]
    sign = 1 if body > 0.0 else -1 if body < 0.0 else 0
    return sign * float(bar["tick_volume"])


def _state(pressure, threshold):
    if pressure == 0.0:
        return 0
    strength = 2 if abs(pressure) >= threshold else 1
    return strength if pressure > 0.0 else -strength


def _pairs(bars, threshold):
    pairs = []
    for index in range(len(bars) - 1):
        state = _state(_pressure(bars[index]), threshold)
        change = bars[index + 1]["close"] - bars[index]["close"]
        if state and change:
            pairs.append((state, 1 if change > 0.0 else 0))
    return pairs


def _binary_entropy(probability):
    if probability <= 0.0 or probability >= 1.0:
        return 0.0
    return -(
        probability * math.log2(probability)
        + (1.0 - probability) * math.log2(1.0 - probability)
    )


def _information_profile(pairs, alpha):
    if len(pairs) < 6:
        return None, {}
    counts = {}
    total_up = 0
    for state, target in pairs:
        bucket = counts.setdefault(state, [0, 0])
        bucket[target] += 1
        total_up += target
    total = len(pairs)
    overall_up = (total_up + alpha) / (total + 2.0 * alpha)
    marginal_entropy = _binary_entropy(overall_up)
    if marginal_entropy <= 0.0:
        return 0.0, counts
    conditional_entropy = 0.0
    for down, up in counts.values():
        state_total = down + up
        probability_up = (up + alpha) / (state_total + 2.0 * alpha)
        conditional_entropy += (
            state_total / total * _binary_entropy(probability_up)
        )
    normalized_gain = max(
        0.0, (marginal_entropy - conditional_entropy) / marginal_entropy
    )
    return normalized_gain, counts


def detect_s392(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return an information-conditioned S392 market payload."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        quantile = float(c["PRESSURE_QUANTILE"])
        alpha = float(c["LAPLACE_ALPHA"])
        info_min = float(c["INFO_GAIN_MIN"])
        info_rise_min = float(c["INFO_GAIN_RISE_MIN"])
        confidence_min = float(c["STATE_CONFIDENCE_MIN"])
        minimum_state = max(1, int(c["MIN_STATE_OBSERVATIONS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not 0.50 <= quantile <= 0.85 or alpha <= 0.0:
        return _wait("Invalid config: pressure quantile or Laplace alpha")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (info_min, info_rise_min)
    ) or not 0.50 <= confidence_min < 1.0:
        return _wait("Invalid config: information gates are invalid")
    required = max(period + 3, baseline_count + recent_count + 1)
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
        threshold = _quantile(
            [abs(_pressure(bar)) for bar in baseline], quantile
        )
        atr = _atr(bars[:-1], period)
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        AttributeError,
        statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if threshold is None or threshold <= 0.0 or atr <= 0.0:
        return _wait("Pressure threshold or ATR is unavailable")
    baseline_info, _ = _information_profile(_pairs(baseline, threshold), alpha)
    recent_info, recent_counts = _information_profile(
        _pairs(recent, threshold), alpha
    )
    if baseline_info is None or recent_info is None:
        return _wait("Information profile is unavailable")
    info_rise = recent_info - baseline_info
    if recent_info < info_min:
        return _wait(f"Recent information gain is weak ({recent_info:.3f})")
    if info_rise < info_rise_min:
        return _wait(f"Information gain has not risen enough ({info_rise:.3f})")

    event_pressure = _pressure(event)
    event_state = _state(event_pressure, threshold)
    down, up = recent_counts.get(event_state, (0, 0))
    support = down + up
    if support < minimum_state:
        return _wait(f"Current pressure state has little support ({support})")
    probability_up = (up + alpha) / (support + 2.0 * alpha)
    confidence = max(probability_up, 1.0 - probability_up)
    if confidence < confidence_min:
        return _wait(f"Current state prediction is uncertain ({confidence:.3f})")
    side = 1 if probability_up > 0.5 else -1

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0:
        return _wait("Event candle is directionless")
    median_volume = statistics.median(
        float(bar["tick_volume"]) for bar in recent
    )
    volume_ratio = event["tick_volume"] / median_volume
    if volume_ratio < float(c["EVENT_VOLUME_RATIO_MIN"]):
        return _wait(f"Event participation is weak ({volume_ratio:.3f}x)")
    if abs(body) < atr * float(c["EVENT_BODY_ATR_MIN"]):
        return _wait("Event body is too small versus ATR")
    if candle_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Event range is too small versus ATR")
    if abs(body) / candle_range < float(c["EVENT_BODY_FRACTION_MIN"]):
        return _wait("Event release lacks body control")

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
        "pattern": f"S392 {signal} Signed-Flow Information Gain {rr:g}R",
        "reason": (
            f"info={recent_info:.4f}, baseline={baseline_info:.4f}, "
            f"rise={info_rise:.4f}, state={event_state}, support={support}, "
            f"p_up={probability_up:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
