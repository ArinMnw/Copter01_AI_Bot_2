# -*- coding: utf-8 -*-
"""S385 — Joint-Tail Bernoulli CUSUM Release 7R.

Baseline upper-tail thresholds classify simultaneous high tick-volume and
high true-range bars.  A one-sided Bernoulli CUSUM then tests whether those
liquidity-consumption events have shifted to a persistently higher arrival
rate in the recent window.  Directional volume inside recent joint-tail
events and a closed release candle determine the continuation side.

All thresholds use older closed bars only.  Market signals fill at the next
open in the simulator, while the closed event extreme plus ATR defines risk.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _quantile, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 80,
    "RECENT_BARS": 20,
    "TAIL_QUANTILE": 0.60,
    "MIN_TAIL_EVENTS": 3,
    "CUSUM_DRIFT": 0.08,
    "CUSUM_MIN": 1.00,
    "TAIL_RATE_RISE_MIN": 0.06,
    "TAIL_DIRECTIONAL_VOLUME_MIN": 0.15,
    "PATH_EFFICIENCY_MIN": 0.20,
    "NET_MOVE_ATR_MIN": 0.45,
    "EVENT_VOLUME_RATIO_MIN": 1.10,
    "EVENT_BODY_ATR_MIN": 0.65,
    "EVENT_RANGE_ATR_MIN": 0.70,
    "EVENT_BODY_FRACTION_MIN": 0.72,
    "EVENT_CLOSE_FRACTION": 0.75,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.19,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 7.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _observations(bars):
    result = []
    travelled = 0.0
    for index in range(1, len(bars)):
        bar = bars[index]
        previous_close = bars[index - 1]["close"]
        true_range = max(
            bar["high"] - bar["low"],
            abs(bar["high"] - previous_close),
            abs(bar["low"] - previous_close),
        )
        result.append((bar["tick_volume"], true_range, bar["close"] - bar["open"]))
        travelled += abs(bar["close"] - previous_close)
    return result, travelled


def _joint_states(observations, volume_threshold, range_threshold):
    return [
        volume >= volume_threshold and true_range >= range_threshold
        for volume, true_range, _ in observations
    ]


def detect_s385(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S385 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(10, int(c["RECENT_BARS"]))
        probability = float(c["TAIL_QUANTILE"])
        minimum_events = max(2, int(c["MIN_TAIL_EVENTS"]))
        drift = float(c["CUSUM_DRIFT"])
        cusum_min = float(c["CUSUM_MIN"])
        rate_rise_min = float(c["TAIL_RATE_RISE_MIN"])
        directional_min = float(c["TAIL_DIRECTIONAL_VOLUME_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_move_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not 0.50 <= probability <= 0.85:
        return _wait("Invalid config: tail quantile outside [0.50, 0.85]")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (drift, cusum_min, rate_rise_min, directional_min, path_min, net_move_min)
    ):
        return _wait("Invalid config: CUSUM gates are invalid")

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
        baseline_observations, _ = _observations(baseline)
        recent_observations, travelled = _observations(recent)
        volume_threshold = _quantile(
            [item[0] for item in baseline_observations], probability
        )
        range_threshold = _quantile(
            [item[1] for item in baseline_observations], probability
        )
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
    if atr <= 0.0 or travelled <= 0.0:
        return _wait("ATR or recent path is zero")
    if volume_threshold is None or range_threshold is None:
        return _wait("Baseline tail thresholds are unavailable")

    baseline_states = _joint_states(
        baseline_observations, volume_threshold, range_threshold
    )
    recent_states = _joint_states(
        recent_observations, volume_threshold, range_threshold
    )
    baseline_rate = sum(baseline_states) / len(baseline_states)
    recent_event_count = sum(recent_states)
    if recent_event_count < minimum_events:
        return _wait(f"Too few recent joint-tail events ({recent_event_count})")
    recent_rate = recent_event_count / len(recent_states)
    rate_rise = recent_rate - baseline_rate
    if rate_rise < rate_rise_min:
        return _wait(f"Joint-tail rate is not expanding ({rate_rise:.3f})")
    cusum = 0.0
    for state in recent_states:
        increment = (1.0 if state else 0.0) - baseline_rate - drift
        cusum = max(0.0, cusum + increment)
    if cusum < cusum_min:
        return _wait(f"Joint-tail CUSUM is weak ({cusum:.3f})")

    event_volume = signed_event_volume = 0.0
    for state, (volume, _, body) in zip(recent_states, recent_observations):
        if state:
            event_volume += volume
            if body != 0.0:
                signed_event_volume += (1.0 if body > 0.0 else -1.0) * volume
    if event_volume <= 0.0:
        return _wait("Recent joint-tail volume is zero")
    directional_volume = signed_event_volume / event_volume
    if abs(directional_volume) < directional_min:
        return _wait(f"Tail directional volume is weak ({directional_volume:.3f})")
    net_move = recent[-1]["close"] - recent[0]["close"]
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Auction path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Auction net move is too small versus ATR")
    side = 1 if net_move > 0.0 else -1
    if side * directional_volume <= 0.0:
        return _wait("Net move and joint-tail volume disagree")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or side * body <= 0.0:
        return _wait("Event does not align with joint-tail CUSUM")
    median_volume = statistics.median(item[0] for item in recent_observations)
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
        if side > 0
        else (event["high"] - event["close"]) / candle_range
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
        if side > 0
        else math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    )
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S385 {signal} Joint-Tail CUSUM Release {rr:g}R",
        "reason": (
            f"tail events={recent_event_count}, CUSUM={cusum:.4f}, "
            f"rate rise={rate_rise:.4f}, directional volume={directional_volume:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
