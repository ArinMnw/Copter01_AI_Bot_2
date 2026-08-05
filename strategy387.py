# -*- coding: utf-8 -*-
"""S387 — Joint-Tail Markov Persistence Release 7R.

Older closed bars define fixed upper-tail thresholds for tick volume and true
range.  The strategy compares Laplace-smoothed joint-tail persistence P(1->1)
in a recent auction with its older baseline.  Rising persistence distinguishes
a sustained liquidity cascade from isolated volume/range spikes.  Directional
tail volume, path efficiency, and a closed release candle select the side.

Market signals fill at the next open in the simulator.  The release extreme
plus ATR defines dynamic short risk without look-ahead or fixed point stops.
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
    "LAPLACE_ALPHA": 1.0,
    "RECENT_P11_MIN": 0.35,
    "P11_RISE_MIN": 0.15,
    "TAIL_DIRECTIONAL_VOLUME_MIN": 0.25,
    "PATH_EFFICIENCY_MIN": 0.20,
    "NET_MOVE_ATR_MIN": 0.45,
    "EVENT_VOLUME_RATIO_MIN": 1.10,
    "EVENT_BODY_ATR_MIN": 0.65,
    "EVENT_RANGE_ATR_MIN": 0.70,
    "EVENT_BODY_FRACTION_MIN": 0.75,
    "EVENT_CLOSE_FRACTION": 0.75,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.19,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    "TP_RR": 7.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _p11(states, alpha):
    """Return smoothed P(next=1 | current=1), hits and opportunities."""
    hits = 0
    opportunities = 0
    for current, following in zip(states[:-1], states[1:]):
        if current:
            opportunities += 1
            if following:
                hits += 1
    probability = (hits + alpha) / (opportunities + 2.0 * alpha)
    return probability, hits, opportunities


def detect_s387(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S387 market payload from fully closed bars."""
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
        alpha = float(c["LAPLACE_ALPHA"])
        recent_p11_min = float(c["RECENT_P11_MIN"])
        p11_rise_min = float(c["P11_RISE_MIN"])
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
    if not math.isfinite(alpha) or alpha <= 0.0:
        return _wait("Invalid config: Laplace alpha must be positive")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (
            recent_p11_min, p11_rise_min, directional_min, path_min, net_move_min
        )
    ):
        return _wait("Invalid config: Markov gates are invalid")

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
    event_count = sum(recent_states)
    if event_count < minimum_events:
        return _wait(f"Too few recent joint-tail events ({event_count})")
    baseline_p11, baseline_hits, baseline_opportunities = _p11(
        baseline_states, alpha
    )
    recent_p11, recent_hits, recent_opportunities = _p11(recent_states, alpha)
    if recent_opportunities < minimum_events - 1:
        return _wait(
            f"Too few recent tail-transition opportunities ({recent_opportunities})"
        )
    persistence_rise = recent_p11 - baseline_p11
    if recent_p11 < recent_p11_min:
        return _wait(f"Recent tail persistence is weak ({recent_p11:.3f})")
    if persistence_rise < p11_rise_min:
        return _wait(f"Tail persistence has not risen enough ({persistence_rise:.3f})")

    tail_volume = 0.0
    signed_tail_volume = 0.0
    for state, (volume, _, body) in zip(recent_states, recent_observations):
        if not state:
            continue
        tail_volume += volume
        if body != 0.0:
            signed_tail_volume += (1.0 if body > 0.0 else -1.0) * volume
    if tail_volume <= 0.0:
        return _wait("Recent joint-tail volume is zero")
    directional_volume = signed_tail_volume / tail_volume
    if abs(directional_volume) < directional_min:
        return _wait(f"Tail direction is weak ({directional_volume:.3f})")

    net_move = recent[-1]["close"] - recent[0]["close"]
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Auction path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Auction net move is too small versus ATR")
    side = 1 if net_move > 0.0 else -1
    if side * directional_volume <= 0.0:
        return _wait("Net move and tail volume disagree")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or side * body <= 0.0:
        return _wait("Event does not align with persistent tail cascade")
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
        "pattern": f"S387 {signal} Joint-Tail Markov Persistence {rr:g}R",
        "reason": (
            f"tail events={event_count}, recent p11={recent_p11:.4f} "
            f"({recent_hits}/{recent_opportunities}), baseline p11={baseline_p11:.4f} "
            f"({baseline_hits}/{baseline_opportunities}), rise={persistence_rise:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
