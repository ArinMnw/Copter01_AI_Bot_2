# -*- coding: utf-8 -*-
"""S384 — Joint-Tail Interarrival Compression Release 7R.

S384 treats simultaneous upper-tail tick-volume and true-range bars as
liquidity-consumption events.  It measures the mean bar gap between those
events.  A shorter recent interarrival clock plus a higher event rate than
disjoint baseline blocks indicates accelerating institutional activity.
Directional volume inside the events and a closed release candle determine
the continuation side.

Only supplied closed bars are inspected.  Entry is represented at the closed
event price and the simulator fills a market signal at the next open.  The
event extreme plus ATR defines risk without fixed points or future data.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _quantile, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 80,
    "RECENT_BARS": 28,
    "TAIL_QUANTILE": 0.60,
    "MIN_TAIL_EVENTS": 3,
    "INTERARRIVAL_COMPRESSION_MIN": 1.15,
    "TAIL_RATE_RISE_MIN": 0.00,
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


def _tail_clock(bars, probability, minimum_events):
    if len(bars) < 10:
        return None
    observations = []
    travelled = 0.0
    for index in range(1, len(bars)):
        bar = bars[index]
        previous_close = bars[index - 1]["close"]
        true_range = max(
            bar["high"] - bar["low"],
            abs(bar["high"] - previous_close),
            abs(bar["low"] - previous_close),
        )
        observations.append((bar["tick_volume"], true_range, bar["close"] - bar["open"]))
        travelled += abs(bar["close"] - previous_close)
    volume_threshold = _quantile([item[0] for item in observations], probability)
    range_threshold = _quantile([item[1] for item in observations], probability)
    if volume_threshold is None or range_threshold is None or travelled <= 0.0:
        return None
    event_indexes = []
    event_volume = signed_event_volume = 0.0
    for index, (volume, true_range, body) in enumerate(observations):
        if volume >= volume_threshold and true_range >= range_threshold:
            event_indexes.append(index)
            event_volume += volume
            if body != 0.0:
                signed_event_volume += (1.0 if body > 0.0 else -1.0) * volume
    if len(event_indexes) < minimum_events or event_volume <= 0.0:
        return None
    gaps = [
        event_indexes[index] - event_indexes[index - 1]
        for index in range(1, len(event_indexes))
    ]
    if not gaps:
        return None
    net_move = bars[-1]["close"] - bars[0]["close"]
    return (
        statistics.mean(gaps),
        len(event_indexes) / len(observations),
        signed_event_volume / event_volume,
        abs(net_move) / travelled,
        net_move,
        statistics.median(item[0] for item in observations),
        len(event_indexes),
    )


def detect_s384(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S384 market payload from fully closed bars."""
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
        compression_min = float(c["INTERARRIVAL_COMPRESSION_MIN"])
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
        for value in (compression_min, rate_rise_min, directional_min, path_min, net_move_min)
    ):
        return _wait("Invalid config: interarrival gates are invalid")

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
        baseline_profiles = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _tail_clock(
                baseline[start:start + recent_count], probability, minimum_events
            )
            if profile is not None:
                baseline_profiles.append(profile)
        recent_profile = _tail_clock(recent, probability, minimum_events)
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
    if atr <= 0.0:
        return _wait("ATR is zero")
    if recent_profile is None or not baseline_profiles:
        return _wait("Joint-tail interarrival profile is unavailable")

    recent_gap, recent_rate, directional_volume, path_efficiency, net_move, median_volume, event_count = recent_profile
    baseline_gap = statistics.median(profile[0] for profile in baseline_profiles)
    baseline_rate = statistics.median(profile[1] for profile in baseline_profiles)
    compression = baseline_gap / recent_gap if recent_gap > 0.0 else 0.0
    rate_rise = recent_rate - baseline_rate
    if compression < compression_min:
        return _wait(f"Tail-event clock is not compressed ({compression:.3f})")
    if rate_rise < rate_rise_min:
        return _wait(f"Tail-event rate is not expanding ({rate_rise:.3f})")
    if abs(directional_volume) < directional_min:
        return _wait(f"Tail directional volume is weak ({directional_volume:.3f})")
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
        return _wait("Event does not align with compressed tail clock")
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
        "pattern": f"S384 {signal} Tail-Clock Compression Release {rr:g}R",
        "reason": (
            f"tail events={event_count}, compression={compression:.4f}, "
            f"rate rise={rate_rise:.4f}, directional volume={directional_volume:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
