# -*- coding: utf-8 -*-
"""S335 - Recurrence-determinism expansion release.

S335 builds a recurrence plot from closed log returns.  Recurrence points that
belong to diagonal lines represent repeated multi-step return trajectories,
rather than isolated values.  Rising recent determinism versus a disjoint
baseline can reveal repeated execution motifs before directional release.

All recurrence and path inputs precede the release candle.  Entry is next-open
market, SL is beyond the closed release extreme plus ATR, and TP is at least
7R.
"""

from __future__ import annotations

import math
from statistics import median

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 64,
    "RECENT_RETURNS": 20,
    "RECURRENCE_EPSILON_MAD": 0.65,
    "RECURRENCE_RATE_MIN": 0.18,
    "RECURRENCE_RATE_MAX": 0.70,
    "RECENT_DETERMINISM_MIN": 0.40,
    "DETERMINISM_JUMP_MIN": 0.12,
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
    "ALLOW_SELL": True,
    "TP_RR": 8.0,
    "BE_RR": 0.08,
    "CANCEL_BARS": 3,
}


def _closed_returns(bars):
    values = []
    for index in range(1, len(bars)):
        previous = float(bars[index - 1]["close"])
        current = float(bars[index]["close"])
        if (
            not math.isfinite(previous)
            or not math.isfinite(current)
            or previous <= 0.0
            or current <= 0.0
        ):
            return None
        values.append(math.log(current / previous))
    return values


def _recurrence_profile(bars, epsilon_multiplier):
    """Return recurrence rate and diagonal determinism for one return sample."""
    values = _closed_returns(bars)
    if values is None or len(values) < 8:
        return None
    centre = median(values)
    mad = median(abs(value - centre) for value in values)
    if mad <= 0.0:
        return None
    epsilon = mad * epsilon_multiplier
    count = len(values)
    recurrent = set()
    for left in range(count - 1):
        for right in range(left + 1, count):
            if abs(values[left] - values[right]) <= epsilon:
                recurrent.add((left, right))
    total_pairs = count * (count - 1) // 2
    if total_pairs <= 0 or not recurrent:
        return 0.0, 0.0

    deterministic = 0
    for left, right in recurrent:
        has_previous = (left - 1, right - 1) in recurrent
        has_next = (left + 1, right + 1) in recurrent
        if has_previous or has_next:
            deterministic += 1
    return len(recurrent) / total_pairs, deterministic / len(recurrent)


def detect_s335(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after return recurrence becomes more deterministic."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_RETURNS"]))
        recent_count = max(8, int(c["RECENT_RETURNS"]))
        epsilon_multiplier = float(c["RECURRENCE_EPSILON_MAD"])
        recurrence_min = float(c["RECURRENCE_RATE_MIN"])
        recurrence_max = float(c["RECURRENCE_RATE_MAX"])
        determinism_min = float(c["RECENT_DETERMINISM_MIN"])
        determinism_jump_min = float(c["DETERMINISM_JUMP_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if (
        not math.isfinite(epsilon_multiplier)
        or epsilon_multiplier <= 0.0
        or not all(
            math.isfinite(value) and 0.0 <= value <= 1.0
            for value in (
                recurrence_min,
                recurrence_max,
                determinism_min,
                determinism_jump_min,
            )
        )
        or recurrence_min > recurrence_max
    ):
        return _wait("Invalid config: recurrence gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 3)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 2:-1]
        baseline = history[:baseline_count + 1]
        recent = history[baseline_count:]
        baseline_profile = _recurrence_profile(
            baseline, epsilon_multiplier
        )
        recent_profile = _recurrence_profile(recent, epsilon_multiplier)
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
    if baseline_profile is None or recent_profile is None:
        return _wait("Recurrence profile is unavailable")

    baseline_rate, baseline_determinism = baseline_profile
    recent_rate, recent_determinism = recent_profile
    determinism_jump = recent_determinism - baseline_determinism
    if not recurrence_min <= recent_rate <= recurrence_max:
        return _wait(f"Recent recurrence rate is outside range ({recent_rate:.3f})")
    if (
        recent_determinism < determinism_min
        or determinism_jump < determinism_jump_min
    ):
        return _wait(
            f"No recurrence-determinism expansion "
            f"({baseline_determinism:.3f}->{recent_determinism:.3f}, "
            f"jump={determinism_jump:.3f})"
        )

    net_move = recent[-1]["close"] - recent[0]["close"]
    travelled = sum(
        abs(recent[index]["close"] - recent[index - 1]["close"])
        for index in range(1, len(recent))
    )
    if travelled <= 0.0:
        return _wait("Recent path has no movement")
    side = 1 if net_move > 0.0 else -1
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes recurrence-path direction")
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
        "pattern": f"S335 {signal} Recurrence Determinism {rr:g}R",
        "reason": (
            f"determinism {baseline_determinism:.4f}->"
            f"{recent_determinism:.4f}, jump={determinism_jump:.4f}, "
            f"recurrence={recent_rate:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
