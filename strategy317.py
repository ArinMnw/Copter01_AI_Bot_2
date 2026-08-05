# -*- coding: utf-8 -*-
"""S317 - Theil-Sen robust slope-acceleration release.

The median of all pairwise slopes gives a high-breakdown trend estimate that
is far less sensitive to one shock candle than OLS.  S317 compares
non-overlapping baseline and recent Theil-Sen slopes, then follows a closed
structural release only when the robust trend has accelerated coherently.

All samples precede the release candle.  Market execution occurs at the next
bar open, with a release-extreme ATR stop and TP of at least 7R.
"""

from __future__ import annotations

import math
from statistics import median

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 36,
    "RECENT_BARS": 14,
    "RECENT_SLOPE_ATR_MIN": 0.040,
    "SLOPE_ACCEL_ATR_MIN": 0.035,
    "PATH_EFFICIENCY_MIN": 0.32,
    "NET_MOVE_ATR_MIN": 0.70,
    "BREAKOUT_LOOKBACK": 10,
    "BREAKOUT_BUFFER_ATR": 0.01,
    "RELEASE_BODY_ATR_MIN": 0.60,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.80,
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


def _theil_sen(values):
    if len(values) < 3:
        return None
    slopes = [
        (values[right] - values[left]) / (right - left)
        for left in range(len(values) - 1)
        for right in range(left + 1, len(values))
    ]
    return median(slopes) if slopes else None


def detect_s317(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a robustly accelerating structural release."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(8, int(c["BASELINE_BARS"]))
        recent_count = max(6, int(c["RECENT_BARS"]))
        breakout_lookback = max(3, int(c["BREAKOUT_LOOKBACK"]))
        slope_min = float(c["RECENT_SLOPE_ATR_MIN"])
        acceleration_min = float(c["SLOPE_ACCEL_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (slope_min, acceleration_min)
    ):
        return _wait("Invalid config: slope thresholds must be finite")

    required = max(
        baseline_count + recent_count + 3,
        period + breakout_lookback + 5,
    )
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside liquid session")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline_closes = [
            bar["close"] for bar in history[:baseline_count]
        ]
        recent_bars = history[baseline_count:]
        recent_closes = [bar["close"] for bar in recent_bars]
        baseline_slope = _theil_sen(baseline_closes)
        recent_slope = _theil_sen(recent_closes)
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
    if baseline_slope is None or recent_slope is None:
        return _wait("Theil-Sen slope is unavailable")
    recent_normalized = recent_slope / atr
    baseline_normalized = baseline_slope / atr
    if abs(recent_normalized) < slope_min:
        return _wait(f"Recent robust slope is weak ({recent_normalized:.4f})")
    side = 1 if recent_normalized > 0.0 else -1
    acceleration = side * (recent_normalized - baseline_normalized)
    if acceleration < acceleration_min:
        return _wait(f"Robust slope is not accelerating ({acceleration:.4f})")

    net_move = recent_closes[-1] - recent_closes[0]
    travelled = sum(
        abs(recent_closes[index] - recent_closes[index - 1])
        for index in range(1, len(recent_closes))
    )
    if travelled <= 0.0:
        return _wait("Recent path has no movement")
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if side * net_move < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move disagrees with robust slope")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes robust acceleration")
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
        "pattern": f"S317 {signal} Theil-Sen Acceleration {rr:g}R",
        "reason": (
            f"Theil-Sen slope {baseline_normalized:.5f}->"
            f"{recent_normalized:.5f}ATR/bar, efficiency={efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
