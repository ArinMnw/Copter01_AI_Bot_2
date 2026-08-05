# -*- coding: utf-8 -*-
"""S386 — Joint-Tail EWMA Hazard Acceleration Release 7R.

Older closed bars define fixed upper-tail thresholds for tick volume and true
range.  Recent simultaneous tail events update fast and slow Bernoulli EWMAs.
A fast hazard above both its baseline rate and the slow hazard identifies a
fresh acceleration in liquidity consumption.  Recency-weighted directional
tail volume and a closed release candle determine the continuation side.

Market signals fill at the next open in the simulator.  The closed release
extreme plus ATR defines dynamic risk without future data or fixed points.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _quantile, _wait
from strategy385 import _joint_states, _observations


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 60,
    "RECENT_BARS": 20,
    "TAIL_QUANTILE": 0.60,
    "MIN_TAIL_EVENTS": 3,
    "FAST_ALPHA": 0.30,
    "SLOW_ALPHA": 0.10,
    "DIRECTION_ALPHA": 0.20,
    "HAZARD_RISE_MIN": 0.12,
    "HAZARD_ACCELERATION_MIN": 0.08,
    "TAIL_DIRECTIONAL_VOLUME_MIN": 0.15,
    "PATH_EFFICIENCY_MIN": 0.20,
    "NET_MOVE_ATR_MIN": 0.45,
    "EVENT_VOLUME_RATIO_MIN": 1.10,
    "EVENT_BODY_ATR_MIN": 0.65,
    "EVENT_RANGE_ATR_MIN": 0.70,
    "EVENT_BODY_FRACTION_MIN": 0.78,
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


def detect_s386(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S386 market payload from fully closed bars."""
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
        fast_alpha = float(c["FAST_ALPHA"])
        slow_alpha = float(c["SLOW_ALPHA"])
        direction_alpha = float(c["DIRECTION_ALPHA"])
        hazard_rise_min = float(c["HAZARD_RISE_MIN"])
        acceleration_min = float(c["HAZARD_ACCELERATION_MIN"])
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
    if not 0.0 < slow_alpha < fast_alpha < 1.0 or not 0.0 < direction_alpha < 1.0:
        return _wait("Invalid config: EWMA alphas are invalid")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (
            hazard_rise_min, acceleration_min, directional_min, path_min, net_move_min
        )
    ):
        return _wait("Invalid config: EWMA gates are invalid")

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
    event_count = sum(recent_states)
    if event_count < minimum_events:
        return _wait(f"Too few recent joint-tail events ({event_count})")
    fast = slow = baseline_rate
    weighted_volume = weighted_signed_volume = 0.0
    for state, (volume, _, body) in zip(recent_states, recent_observations):
        state_value = 1.0 if state else 0.0
        fast = (1.0 - fast_alpha) * fast + fast_alpha * state_value
        slow = (1.0 - slow_alpha) * slow + slow_alpha * state_value
        weighted_volume *= 1.0 - direction_alpha
        weighted_signed_volume *= 1.0 - direction_alpha
        if state:
            weighted_volume += direction_alpha * volume
            if body != 0.0:
                weighted_signed_volume += (
                    direction_alpha * (1.0 if body > 0.0 else -1.0) * volume
                )
    hazard_rise = fast - baseline_rate
    acceleration = fast - slow
    if hazard_rise < hazard_rise_min:
        return _wait(f"Fast tail hazard is not elevated ({hazard_rise:.3f})")
    if acceleration < acceleration_min:
        return _wait(f"Tail hazard is not accelerating ({acceleration:.3f})")
    if weighted_volume <= 0.0:
        return _wait("Weighted joint-tail volume is zero")
    directional_volume = weighted_signed_volume / weighted_volume
    if abs(directional_volume) < directional_min:
        return _wait(f"Weighted tail direction is weak ({directional_volume:.3f})")

    net_move = recent[-1]["close"] - recent[0]["close"]
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Auction path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Auction net move is too small versus ATR")
    side = 1 if net_move > 0.0 else -1
    if side * directional_volume <= 0.0:
        return _wait("Net move and weighted tail volume disagree")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or side * body <= 0.0:
        return _wait("Event does not align with accelerated tail hazard")
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
        "pattern": f"S386 {signal} Joint-Tail EWMA Hazard Release {rr:g}R",
        "reason": (
            f"tail events={event_count}, fast={fast:.4f}, slow={slow:.4f}, "
            f"rise={hazard_rise:.4f}, acceleration={acceleration:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
