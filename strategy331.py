# -*- coding: utf-8 -*-
"""S331 - Runs-declustered extremal-index release.

Absolute-return exceedances are defined from a baseline empirical quantile.
Consecutive exceedances separated by no more than a small run gap are grouped
into one cluster.  The clusters-to-events ratio is a runs extremal-index proxy:
lower values indicate that tail events are arriving in self-contained bursts
rather than independently.

All extreme-event inputs precede the release candle.  Entry is next-open
market, the stop is beyond the release extreme plus ATR, and TP is at least 7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 64,
    "RECENT_RETURNS": 20,
    "EVENT_QUANTILE": 0.75,
    "DECLUSTER_GAP": 2,
    "RECENT_EVENT_MIN": 5,
    "RECENT_EXTREMAL_INDEX_MAX": 0.65,
    "EXTREMAL_INDEX_DROP_MIN": 0.12,
    "DIRECTION_SCORE_MIN": 0.20,
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


def _quantile(values, probability):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _closed_returns(bars):
    values = []
    for index in range(1, len(bars)):
        previous = float(bars[index - 1]["close"])
        current = float(bars[index]["close"])
        if previous <= 0.0 or current <= 0.0:
            return None
        values.append(math.log(current / previous))
    return values


def _extreme_state(values, threshold, run_gap):
    event_indices = [
        index for index, value in enumerate(values)
        if abs(value) >= threshold
    ]
    if not event_indices:
        return None
    clusters = 1 + sum(
        current - previous > run_gap
        for previous, current in zip(event_indices, event_indices[1:])
    )
    event_returns = [values[index] for index in event_indices]
    magnitude = sum(abs(value) for value in event_returns)
    if magnitude <= 0.0:
        return None
    return {
        "events": len(event_indices),
        "clusters": clusters,
        "theta": clusters / len(event_indices),
        "direction": sum(event_returns) / magnitude,
    }


def detect_s331(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release when extreme returns become directionally clustered."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_RETURNS"]))
        recent_count = max(8, int(c["RECENT_RETURNS"]))
        probability = float(c["EVENT_QUANTILE"])
        run_gap = max(1, int(c["DECLUSTER_GAP"]))
        event_min = max(2, int(c["RECENT_EVENT_MIN"]))
        theta_max = float(c["RECENT_EXTREMAL_INDEX_MAX"])
        theta_drop_min = float(c["EXTREMAL_INDEX_DROP_MIN"])
        direction_min = float(c["DIRECTION_SCORE_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if (
        not math.isfinite(probability)
        or not 0.50 <= probability <= 0.95
        or not all(
            math.isfinite(value) and value > 0.0
            for value in (theta_max, theta_drop_min, direction_min)
        )
    ):
        return _wait("Invalid config: extremal-index gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 3)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 2:-1]
        returns = _closed_returns(history)
        baseline_returns = returns[:baseline_count]
        recent_returns = returns[baseline_count:]
        threshold = _quantile(
            [abs(value) for value in baseline_returns], probability
        )
        baseline_state = (
            None if threshold is None else _extreme_state(
                baseline_returns, threshold, run_gap
            )
        )
        recent_state = (
            None if threshold is None else _extreme_state(
                recent_returns, threshold, run_gap
            )
        )
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
    if baseline_state is None or recent_state is None:
        return _wait("Extremal index is unavailable")
    theta_drop = baseline_state["theta"] - recent_state["theta"]
    if (
        recent_state["events"] < event_min
        or recent_state["theta"] > theta_max
        or theta_drop < theta_drop_min
    ):
        return _wait(
            f"No extremal clustering ({recent_state['events']} events, "
            f"theta={recent_state['theta']:.3f}, drop={theta_drop:.3f})"
        )
    if abs(recent_state["direction"]) < direction_min:
        return _wait(
            f"Extreme-cluster direction is weak "
            f"({recent_state['direction']:.3f})"
        )
    side = 1 if recent_state["direction"] > 0.0 else -1

    recent = history[baseline_count:]
    net_move = recent[-1]["close"] - recent[0]["close"]
    travelled = sum(
        abs(recent[index]["close"] - recent[index - 1]["close"])
        for index in range(1, len(recent))
    )
    if travelled <= 0.0:
        return _wait("Recent path has no movement")
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move is too small")
    if net_move * side <= 0.0:
        return _wait("Recent path opposes extreme-cluster direction")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes extreme-cluster direction")
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
        "pattern": f"S331 {signal} Extremal-Index Cluster {rr:g}R",
        "reason": (
            f"extremal index {baseline_state['theta']:.4f}->"
            f"{recent_state['theta']:.4f}, drop={theta_drop:.4f}, "
            f"events={recent_state['events']}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
