# -*- coding: utf-8 -*-
"""S400 — Gini Return–Volume Rank-Coupling Release 7R.

Closed returns are coupled to empirical tick-volume ranks through a normalized
Gini-covariance score.  The statistic is robust to the scale and outliers of
raw volume: positive values mean higher returns align with higher volume ranks,
while negative values imply the opposite directional auction.  Recent absolute
coupling must strengthen from disjoint baseline blocks and agree with net path,
participation, and a closed release candle.  Execution is next-open market with
an event-extreme plus ATR stop and at least 7R reward.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 24,
    "GINI_COUPLING_MIN": 0.20,
    "GINI_COUPLING_RISE_MIN": 0.13,
    "PATH_EFFICIENCY_MIN": 0.14,
    "NET_MOVE_ATR_MIN": 0.30,
    "EVENT_VOLUME_RATIO_MIN": 1.05,
    "EVENT_BODY_ATR_MIN": 0.65,
    "EVENT_RANGE_ATR_MIN": 0.75,
    "EVENT_BODY_FRACTION_MIN": 0.72,
    "EVENT_CLOSE_FRACTION": 0.75,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.22,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 7.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _average_ranks(values):
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        average = (cursor + end - 1) / 2.0
        for position in range(cursor, end):
            ranks[order[position]] = average
        cursor = end
    return ranks


def _gini_coupling(bars):
    returns = [
        bars[index]["close"] - bars[index - 1]["close"]
        for index in range(1, len(bars))
    ]
    volumes = [float(bar["tick_volume"]) for bar in bars[1:]]
    if len(returns) < 8:
        return None, 0.0
    mean_return = statistics.fmean(returns)
    centred = [value - mean_return for value in returns]
    absolute_sum = sum(abs(value) for value in centred)
    if absolute_sum <= 0.0:
        return None, 0.0
    ranks = _average_ranks(volumes)
    midpoint = (len(ranks) - 1) / 2.0
    scale = max(midpoint, 1.0)
    rank_scores = [(rank - midpoint) / scale for rank in ranks]
    coupling = sum(
        value * score for value, score in zip(centred, rank_scores)
    ) / absolute_sum
    travelled = sum(abs(value) for value in returns)
    return coupling, travelled


def detect_s400(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S400 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        coupling_min = float(c["GINI_COUPLING_MIN"])
        rise_min = float(c["GINI_COUPLING_RISE_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_move_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: Gini-coupling windows are inconsistent")
    gates = (coupling_min, rise_min, path_min, net_move_min)
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: Gini-coupling gates are invalid")
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
        segment_count = baseline_count // recent_count
        baseline = baseline[-segment_count * recent_count:]
        baseline_scores = [
            _gini_coupling(baseline[index:index + recent_count])[0]
            for index in range(0, len(baseline), recent_count)
        ]
        recent_coupling, travelled = _gini_coupling(recent)
        baseline_abs = statistics.median(abs(value) for value in baseline_scores)
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if recent_coupling is None or atr <= 0.0:
        return _wait("Gini coupling or ATR is unavailable")
    side = 1 if recent_coupling >= 0.0 else -1
    coupling_strength = abs(recent_coupling)
    coupling_rise = coupling_strength - baseline_abs
    if coupling_strength < coupling_min:
        return _wait(f"Recent Gini coupling is weak ({coupling_strength:.3f})")
    if coupling_rise < rise_min:
        return _wait(f"Gini coupling has not expanded ({coupling_rise:.3f})")
    if travelled <= 0.0:
        return _wait("Recent path is zero")
    net_move = recent[-1]["close"] - recent[0]["close"]
    path_efficiency = abs(net_move) / travelled
    if side * net_move <= 0.0 or path_efficiency < path_min:
        return _wait(f"Auction path does not confirm coupling ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Net move is too small versus ATR")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or side * body <= 0.0:
        return _wait("Event does not confirm Gini-coupling direction")
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
        "pattern": f"S400 {signal} Gini Return-Volume Coupling {rr:g}R",
        "reason": (
            f"gini_coupling={recent_coupling:.4f}, baseline_abs={baseline_abs:.4f}, "
            f"rise={coupling_rise:.4f}, path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
