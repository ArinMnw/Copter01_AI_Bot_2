# -*- coding: utf-8 -*-
"""S397 — Bowley Quantile-Skew Rotation Release 7R.

The strategy measures robust return asymmetry with Bowley's quartile skewness,
which depends on Q1, the median, and Q3 rather than unstable third moments.  A
recent directional skew must be material and rotate away from the baseline in
the same direction.  Directional path, displacement, participation, and a
fully closed release candle confirm execution.  Orders fill at the next open;
the stop lies beyond the event extreme with an ATR-scaled buffer.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 80,
    "RECENT_BARS": 24,
    "BOWLEY_SKEW_MIN": 0.14,
    "BOWLEY_ROTATION_MIN": 0.08,
    "QUARTILE_SPREAD_ATR_MIN": 0.08,
    "PATH_EFFICIENCY_MIN": 0.14,
    "NET_MOVE_ATR_MIN": 0.30,
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


def _quantile(sorted_values, probability):
    position = (len(sorted_values) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def _bowley(values):
    ordered = sorted(values)
    q1 = _quantile(ordered, 0.25)
    median = _quantile(ordered, 0.50)
    q3 = _quantile(ordered, 0.75)
    spread = q3 - q1
    if spread <= 0.0:
        return None, 0.0
    return (q3 + q1 - 2.0 * median) / spread, spread


def detect_s397(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S397 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        skew_min = float(c["BOWLEY_SKEW_MIN"])
        rotation_min = float(c["BOWLEY_ROTATION_MIN"])
        spread_min = float(c["QUARTILE_SPREAD_ATR_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_move_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: quantile-skew windows are inconsistent")
    gates = (skew_min, rotation_min, spread_min, path_min, net_move_min)
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: quantile-skew gates are invalid")
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
        baseline_skew, _ = _bowley(_returns(baseline))
        recent_returns = _returns(recent)
        recent_skew, quartile_spread = _bowley(recent_returns)
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if baseline_skew is None or recent_skew is None or atr <= 0.0:
        return _wait("Bowley skew or ATR is unavailable")
    side = 1 if recent_skew >= 0.0 else -1
    skew_strength = side * recent_skew
    rotation = side * (recent_skew - baseline_skew)
    if skew_strength < skew_min:
        return _wait(f"Recent Bowley skew is weak ({skew_strength:.3f})")
    if rotation < rotation_min:
        return _wait(f"Bowley skew has not rotated ({rotation:.3f})")
    if quartile_spread < atr * spread_min:
        return _wait("Recent interquartile return spread is too narrow")
    travelled = sum(abs(value) for value in recent_returns)
    if travelled <= 0.0:
        return _wait("Recent path is zero")
    net_move = recent[-1]["close"] - recent[0]["close"]
    path_efficiency = abs(net_move) / travelled
    if side * net_move <= 0.0 or path_efficiency < path_min:
        return _wait(f"Auction path does not confirm skew ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Net move is too small versus ATR")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or side * body <= 0.0:
        return _wait("Event does not confirm quantile-skew direction")
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
        "pattern": f"S397 {signal} Bowley Quantile-Skew Rotation {rr:g}R",
        "reason": (
            f"bowley={recent_skew:.4f}, baseline={baseline_skew:.4f}, "
            f"rotation={rotation:.4f}, iqr={quartile_spread:.4f}, "
            f"path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }

