# -*- coding: utf-8 -*-
"""S383 — Volume-Range Upper-Tail Co-exceedance Release 7R.

The detector measures how often tick volume and true range enter their upper
tails together.  A recent rise in joint-tail lift versus disjoint baseline
blocks indicates that participation is consuming liquidity nonlinearly rather
than merely accompanying ordinary noise.  Directional volume inside those
joint-tail bars identifies the auction side; a closed release candle confirms
entry at the next bar open.

Only supplied closed bars are inspected.  The event extreme plus ATR defines
dynamic risk; no fixed-point stop or future price is used.
"""

from __future__ import annotations

import math
import statistics


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 80,
    "RECENT_BARS": 28,
    "TAIL_QUANTILE": 0.60,
    "JOINT_RATE_MIN": 0.18,
    "TAIL_LIFT_MIN": 1.25,
    "TAIL_LIFT_RISE_MIN": 0.08,
    "TAIL_DIRECTIONAL_VOLUME_MIN": 0.15,
    "PATH_EFFICIENCY_MIN": 0.20,
    "NET_MOVE_ATR_MIN": 0.45,
    "EVENT_VOLUME_RATIO_MIN": 1.10,
    "EVENT_BODY_ATR_MIN": 0.50,
    "EVENT_RANGE_ATR_MIN": 0.70,
    "EVENT_BODY_FRACTION_MIN": 0.70,
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


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite rate value")
    return number


def _bars(rates):
    result = []
    previous_time = None
    for raw in rates:
        timestamp = int(_finite(raw["time"]))
        if previous_time is not None and timestamp <= previous_time:
            raise ValueError("rates must be chronological")
        previous_time = timestamp
        bar = {
            "time": timestamp,
            "open": _finite(raw["open"]),
            "high": _finite(raw["high"]),
            "low": _finite(raw["low"]),
            "close": _finite(raw["close"]),
            "tick_volume": max(1.0, _finite(raw["tick_volume"])),
        }
        if bar["high"] < max(bar["open"], bar["close"], bar["low"]):
            raise ValueError("invalid high")
        if bar["low"] > min(bar["open"], bar["close"], bar["high"]):
            raise ValueError("invalid low")
        if min(bar["open"], bar["high"], bar["low"], bar["close"]) <= 0.0:
            raise ValueError("prices must be positive")
        result.append(bar)
    return result


def _atr(bars, period):
    if period < 1 or len(bars) < period + 1:
        return 0.0
    values = []
    for index in range(len(bars) - period, len(bars)):
        bar = bars[index]
        previous_close = bars[index - 1]["close"]
        values.append(max(
            bar["high"] - bar["low"],
            abs(bar["high"] - previous_close),
            abs(bar["low"] - previous_close),
        ))
    return sum(values) / len(values)


def _quantile(values, probability):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _tail_profile(bars, probability):
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
    volume_hits = range_hits = joint_hits = 0
    joint_volume = signed_joint_volume = 0.0
    for volume, true_range, body in observations:
        volume_high = volume >= volume_threshold
        range_high = true_range >= range_threshold
        volume_hits += int(volume_high)
        range_hits += int(range_high)
        if volume_high and range_high:
            joint_hits += 1
            joint_volume += volume
            if body != 0.0:
                signed_joint_volume += (1.0 if body > 0.0 else -1.0) * volume
    count = len(observations)
    volume_rate = volume_hits / count
    range_rate = range_hits / count
    joint_rate = joint_hits / count
    expected = volume_rate * range_rate
    if expected <= 0.0 or joint_volume <= 0.0:
        return None
    net_move = bars[-1]["close"] - bars[0]["close"]
    return (
        joint_rate,
        joint_rate / expected,
        signed_joint_volume / joint_volume,
        abs(net_move) / travelled,
        net_move,
        statistics.median(item[0] for item in observations),
    )


def detect_s383(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S383 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(10, int(c["RECENT_BARS"]))
        probability = float(c["TAIL_QUANTILE"])
        joint_rate_min = float(c["JOINT_RATE_MIN"])
        lift_min = float(c["TAIL_LIFT_MIN"])
        lift_rise_min = float(c["TAIL_LIFT_RISE_MIN"])
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
        for value in (
            joint_rate_min,
            lift_min,
            lift_rise_min,
            directional_min,
            path_min,
            net_move_min,
        )
    ):
        return _wait("Invalid config: tail-coupling gates are invalid")

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
        baseline_lifts = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _tail_profile(baseline[start:start + recent_count], probability)
            if profile is not None:
                baseline_lifts.append(profile[1])
        recent_profile = _tail_profile(recent, probability)
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
    if recent_profile is None or not baseline_lifts:
        return _wait("Volume-range tail profile is unavailable")

    joint_rate, lift, directional_volume, path_efficiency, net_move, median_volume = recent_profile
    lift_rise = lift - statistics.median(baseline_lifts)
    if joint_rate < joint_rate_min:
        return _wait(f"Joint-tail rate is weak ({joint_rate:.3f})")
    if lift < lift_min:
        return _wait(f"Joint-tail lift is weak ({lift:.3f})")
    if lift_rise < lift_rise_min:
        return _wait(f"No joint-tail expansion ({lift_rise:.3f})")
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
        return _wait("Event does not align with tail-coupled auction")
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
        "pattern": f"S383 {signal} Upper-Tail Coupling Release {rr:g}R",
        "reason": (
            f"joint={joint_rate:.4f}, lift={lift:.4f}, rise={lift_rise:.4f}, "
            f"tail directional volume={directional_volume:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
