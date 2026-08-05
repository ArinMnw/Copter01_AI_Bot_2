# -*- coding: utf-8 -*-
"""S411 — Tail-Range Wick-Absorption Release 7R.

S411 conditions wick asymmetry on the largest-range candles in each block.
Lower-wick dominance represents bid-side absorption and upper-wick dominance
offer-side absorption.  Recent tail imbalance must strengthen versus disjoint
baseline blocks before a fully closed participated event confirms direction.
Orders fill next-open with an event-extreme ATR stop and at least a 7R target.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 60,
    "RECENT_BARS": 20,
    "TAIL_QUANTILE": 0.70,
    "IMBALANCE_ABS_MIN": 0.10,
    "IMBALANCE_RATIO_MIN": 1.20,
    "IMBALANCE_RISE_MIN": 0.04,
    "TAIL_RANGE_RATIO_MIN": 1.15,
    "PATH_EFFICIENCY_MIN": 0.06,
    "NET_MOVE_ATR_MIN": 0.20,
    "REQUIRE_PATH_ALIGNMENT": False,
    "FADE_IMBALANCE": False,
    "EVENT_VOLUME_RATIO_MIN": 1.00,
    "EVENT_BODY_ATR_MIN": 0.45,
    "EVENT_RANGE_ATR_MIN": 0.65,
    "EVENT_BODY_FRACTION_MIN": 0.58,
    "EVENT_CLOSE_FRACTION": 0.68,
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


def _linear_quantile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _tail_wick_metrics(bars, quantile):
    if len(bars) < 9:
        return None
    ranges = [bar["high"] - bar["low"] for bar in bars]
    if any(value <= 0.0 for value in ranges):
        return None
    threshold = _linear_quantile(ranges, quantile)
    selected = []
    selected_ranges = []
    for bar, candle_range in zip(bars, ranges):
        if candle_range < threshold:
            continue
        upper = bar["high"] - max(bar["open"], bar["close"])
        lower = min(bar["open"], bar["close"]) - bar["low"]
        selected.append((lower - upper) / candle_range)
        selected_ranges.append(candle_range)
    if len(selected) < 3:
        return None
    median_range = statistics.median(ranges)
    if median_range <= 0.0:
        return None
    return {
        "imbalance": statistics.fmean(selected),
        "tail_range_ratio": statistics.median(selected_ranges) / median_range,
        "tail_count": len(selected),
    }


def detect_s411(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S411 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        quantile = float(c["TAIL_QUANTILE"])
        imbalance_min = float(c["IMBALANCE_ABS_MIN"])
        ratio_min = float(c["IMBALANCE_RATIO_MIN"])
        rise_min = float(c["IMBALANCE_RISE_MIN"])
        tail_range_min = float(c["TAIL_RANGE_RATIO_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: wick windows are inconsistent")
    if not 0.50 <= quantile <= 0.90:
        return _wait("Invalid config: tail quantile is invalid")
    gates = (imbalance_min, ratio_min, rise_min, tail_range_min, path_min, net_min)
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: wick gates are invalid")
    required = max(period + 3, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured absorption window")
    try:
        bars = _bars(rates[-required:])
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        segment_count = baseline_count // recent_count
        baseline = baseline[-segment_count * recent_count:]
        baseline_metrics = [
            _tail_wick_metrics(baseline[index:index + recent_count], quantile)
            for index in range(0, len(baseline), recent_count)
        ]
        recent_metrics = _tail_wick_metrics(recent, quantile)
        if recent_metrics is None or any(item is None for item in baseline_metrics):
            return _wait("Tail-wick imbalance is unavailable")
        baseline_strength = statistics.median(
            abs(item["imbalance"]) for item in baseline_metrics
        )
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is unavailable")
    imbalance = recent_metrics["imbalance"]
    strength = abs(imbalance)
    ratio = strength / max(baseline_strength, 1e-9)
    rise = strength - baseline_strength
    if strength < imbalance_min:
        return _wait(f"Tail-wick imbalance is weak ({strength:.3f})")
    if ratio < ratio_min:
        return _wait(f"Tail-wick ratio is weak ({ratio:.3f})")
    if rise < rise_min:
        return _wait(f"Tail-wick rise is weak ({rise:.3f})")
    if recent_metrics["tail_range_ratio"] < tail_range_min:
        return _wait("Tail candles are not distinct from median range")
    wick_side = 1 if imbalance > 0.0 else -1
    trade_side = -wick_side if bool(c["FADE_IMBALANCE"]) else wick_side

    returns = [recent[index]["close"] - recent[index - 1]["close"]
               for index in range(1, len(recent))]
    travelled = sum(abs(value) for value in returns)
    net_move = recent[-1]["close"] - recent[0]["close"]
    if travelled <= 0.0 or net_move == 0.0:
        return _wait("Recent path is unavailable")
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Absorption path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_min:
        return _wait("Absorption move is too small versus ATR")
    if bool(c["REQUIRE_PATH_ALIGNMENT"]) and trade_side * net_move <= 0.0:
        return _wait("Price path disagrees with wick absorption")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or trade_side * body <= 0.0:
        return _wait("Event direction does not confirm wick absorption")
    median_volume = statistics.median(float(bar["tick_volume"]) for bar in recent)
    if median_volume <= 0.0:
        return _wait("Recent volume is unavailable")
    volume_ratio = event["tick_volume"] / median_volume
    if volume_ratio < float(c["EVENT_VOLUME_RATIO_MIN"]):
        return _wait(f"Event participation is weak ({volume_ratio:.3f}x)")
    if abs(body) < atr * float(c["EVENT_BODY_ATR_MIN"]):
        return _wait("Event body is too small versus ATR")
    if candle_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Event range is too small versus ATR")
    if abs(body) / candle_range < float(c["EVENT_BODY_FRACTION_MIN"]):
        return _wait("Event lacks directional body control")
    location = ((event["close"] - event["low"]) / candle_range
                if trade_side > 0 else (event["high"] - event["close"]) / candle_range)
    if location < float(c["EVENT_CLOSE_FRACTION"]):
        return _wait(f"Event close lacks directional control ({location:.3f})")

    signal = "BUY" if trade_side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(event["close"], 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if trade_side > 0:
        sl = math.floor((event["low"] - sl_buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + sl_buffer - 1e-12) * 100.0) / 100.0
    risk = trade_side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Event risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Event risk too large versus price")
    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + trade_side * rr * risk
    tp = (math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
          if trade_side > 0 else math.floor((raw_tp + 1e-12) * 100.0) / 100.0)
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S411 {signal} Tail-Wick Absorption {rr:g}R",
        "reason": (
            f"imbalance={imbalance:.4f}, baseline={baseline_strength:.4f}, "
            f"ratio={ratio:.3f}, rise={rise:.3f}, "
            f"tail_range={recent_metrics['tail_range_ratio']:.3f}, "
            f"path={path_efficiency:.3f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
