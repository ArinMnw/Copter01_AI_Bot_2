# -*- coding: utf-8 -*-
"""S396 — Studentized Return-CUSUM Drift-Shift Release 7R.

The strategy estimates a stable mean and scale from closed baseline returns,
then feeds recent standardized residuals into a two-sided Page CUSUM.  A large,
dominant, and still-accelerating terminal excursion identifies an active drift
change rather than an isolated candle.  Directional path and a participated
release candle confirm the trade.  Execution is next-open market with an
event-extreme, ATR-scaled stop and at least 7R reward.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 80,
    "RECENT_BARS": 24,
    "CUSUM_ALLOWANCE": 0.30,
    "CUSUM_STRENGTH_MIN": 4.0,
    "CUSUM_DOMINANCE_MIN": 0.45,
    "CUSUM_RISE_MIN": 1.0,
    "MEAN_SHIFT_Z_MIN": 0.18,
    "PATH_EFFICIENCY_MIN": 0.16,
    "NET_MOVE_ATR_MIN": 0.35,
    "EVENT_VOLUME_RATIO_MIN": 1.05,
    "EVENT_BODY_ATR_MIN": 0.65,
    "EVENT_RANGE_ATR_MIN": 0.75,
    "EVENT_BODY_FRACTION_MIN": 0.72,
    "EVENT_CLOSE_FRACTION": 0.75,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.18,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 7.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _returns(bars):
    return [
        bars[index]["close"] - bars[index - 1]["close"]
        for index in range(1, len(bars))
    ]


def _terminal_cusum(values, allowance):
    positive = negative = 0.0
    mid_positive = mid_negative = 0.0
    midpoint = len(values) // 2
    for index, value in enumerate(values, 1):
        positive = max(0.0, positive + value - allowance)
        negative = max(0.0, negative - value - allowance)
        if index == midpoint:
            mid_positive, mid_negative = positive, negative
    return positive, negative, mid_positive, mid_negative


def detect_s396(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S396 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        allowance = float(c["CUSUM_ALLOWANCE"])
        strength_min = float(c["CUSUM_STRENGTH_MIN"])
        dominance_min = float(c["CUSUM_DOMINANCE_MIN"])
        rise_min = float(c["CUSUM_RISE_MIN"])
        mean_shift_min = float(c["MEAN_SHIFT_Z_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_move_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: CUSUM windows are inconsistent")
    gates = (
        allowance, strength_min, dominance_min, rise_min, mean_shift_min,
        path_min, net_move_min,
    )
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: CUSUM gates are invalid")
    if dominance_min > 1.0:
        return _wait("Invalid config: CUSUM dominance exceeds one")
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
        baseline_returns = _returns(baseline)
        recent_returns = _returns(recent)
        baseline_mean = statistics.fmean(baseline_returns)
        baseline_scale = statistics.pstdev(baseline_returns)
        standardized = [
            (value - baseline_mean) / baseline_scale for value in recent_returns
        ]
        positive, negative, mid_positive, mid_negative = _terminal_cusum(
            standardized, allowance
        )
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if baseline_scale <= 0.0 or atr <= 0.0:
        return _wait("Baseline scale or ATR is unavailable")
    side = 1 if positive >= negative else -1
    strength = positive if side > 0 else negative
    opposite = negative if side > 0 else positive
    midpoint_strength = mid_positive if side > 0 else mid_negative
    dominance = (strength - opposite) / max(strength + opposite, 1e-12)
    rise = strength - midpoint_strength
    mean_shift_z = side * statistics.fmean(standardized)
    if strength < strength_min:
        return _wait(f"Terminal CUSUM is weak ({strength:.3f})")
    if dominance < dominance_min:
        return _wait(f"CUSUM direction is ambiguous ({dominance:.3f})")
    if rise < rise_min:
        return _wait(f"CUSUM is not accelerating ({rise:.3f})")
    if mean_shift_z < mean_shift_min:
        return _wait(f"Mean shift is weak ({mean_shift_z:.3f}z)")
    travelled = sum(abs(value) for value in recent_returns)
    if travelled <= 0.0:
        return _wait("Recent path is zero")
    net_move = recent[-1]["close"] - recent[0]["close"]
    path_efficiency = abs(net_move) / travelled
    if side * net_move <= 0.0 or path_efficiency < path_min:
        return _wait(f"Auction path does not confirm CUSUM ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Net move is too small versus ATR")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or side * body <= 0.0:
        return _wait("Event does not confirm CUSUM direction")
    median_volume = statistics.median(float(bar["tick_volume"]) for bar in recent)
    volume_ratio = event["tick_volume"] / median_volume
    if volume_ratio < float(c["EVENT_VOLUME_RATIO_MIN"]):
        return _wait(f"Event participation is weak ({volume_ratio:.3f}x)")
    if abs(body) < atr * float(c["EVENT_BODY_ATR_MIN"]):
        return _wait("Event body is too small versus ATR")
    if candle_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Event range is too small versus ATR")
    if abs(body) / candle_range < float(c["EVENT_BODY_FRACTION_MIN"]):
        return _wait("Event release lacks body control")
    location = (
        (event["close"] - event["low"]) / candle_range
        if side > 0 else (event["high"] - event["close"]) / candle_range
    )
    if location < float(c["EVENT_CLOSE_FRACTION"]):
        return _wait(f"Event close lacks directional control ({location:.3f})")

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
        if side > 0 else math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    )
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S396 {signal} Studentized CUSUM Drift Shift {rr:g}R",
        "reason": (
            f"cusum={strength:.4f}, dominance={dominance:.4f}, "
            f"rise={rise:.4f}, mean_shift={mean_shift_z:.4f}z, "
            f"path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
