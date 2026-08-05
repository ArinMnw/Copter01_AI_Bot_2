# -*- coding: utf-8 -*-
"""S403 — Realized-Semivariance Dominance Exhaustion 7R.

Positive and negative realized semivariances split return energy by direction.
S403 looks for a recent one-sided variance share that expands above disjoint
baseline blocks, agrees with the net auction path, and is followed by a fully
closed participated release.  The default hypothesis fades this statistically
crowded move at next open, with the stop beyond the event extreme and a target
of at least 7R.  Only closed bars are inspected.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 24,
    "DOMINANCE_MIN": 0.66,
    "DOMINANCE_RATIO_MIN": 1.04,
    "DOMINANCE_RISE_MIN": 0.02,
    "DOMINANT_ENERGY_ATR2_MIN": 0.05,
    "PATH_EFFICIENCY_MIN": 0.12,
    "NET_MOVE_ATR_MIN": 0.28,
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
    "FADE_DOMINANCE": False,
    "TP_RR": 9.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _returns(bars):
    return [
        bars[index]["close"] - bars[index - 1]["close"]
        for index in range(1, len(bars))
    ]


def _semivariance_metrics(values):
    if len(values) < 8:
        return None
    positive = sum(value * value for value in values if value > 0.0)
    negative = sum(value * value for value in values if value < 0.0)
    total = positive + negative
    if not math.isfinite(total) or total <= 0.0:
        return None
    side = 1 if positive >= negative else -1
    dominant = max(positive, negative)
    return dominant / total, dominant, side


def detect_s403(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S403 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        dominance_min = float(c["DOMINANCE_MIN"])
        ratio_min = float(c["DOMINANCE_RATIO_MIN"])
        rise_min = float(c["DOMINANCE_RISE_MIN"])
        energy_min = float(c["DOMINANT_ENERGY_ATR2_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_move_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: semivariance windows are inconsistent")
    gates = (dominance_min, ratio_min, rise_min, energy_min, path_min, net_move_min)
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: semivariance gates are invalid")
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
        baseline_metrics = [
            _semivariance_metrics(_returns(baseline[index:index + recent_count]))
            for index in range(0, len(baseline), recent_count)
        ]
        recent_returns = _returns(recent)
        recent_metrics = _semivariance_metrics(recent_returns)
        if recent_metrics is None or any(
            metrics is None for metrics in baseline_metrics
        ):
            return _wait("Semivariance is unavailable")
        baseline_dominance = statistics.median(
            metrics[0] for metrics in baseline_metrics
        )
        recent_dominance, dominant_energy, path_side = recent_metrics
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is unavailable")
    if recent_dominance < dominance_min:
        return _wait(f"Semivariance dominance is weak ({recent_dominance:.3f})")
    dominance_ratio = recent_dominance / max(baseline_dominance, 1e-9)
    dominance_rise = recent_dominance - baseline_dominance
    energy_atr2 = dominant_energy / len(recent_returns) / (atr * atr)
    if dominance_ratio < ratio_min:
        return _wait(f"Dominance ratio is weak ({dominance_ratio:.3f})")
    if dominance_rise < rise_min:
        return _wait(f"Dominance rise is weak ({dominance_rise:.3f})")
    if energy_atr2 < energy_min:
        return _wait(f"Dominant energy is weak ({energy_atr2:.3f} ATR2)")

    travelled = sum(abs(value) for value in recent_returns)
    if travelled <= 0.0:
        return _wait("Recent path is zero")
    net_move = recent[-1]["close"] - recent[0]["close"]
    net_side = 1 if net_move > 0.0 else -1
    if net_side != path_side:
        return _wait("Net path disagrees with semivariance side")
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Auction path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Net move is too small versus ATR")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or path_side * body <= 0.0:
        return _wait("Event does not confirm semivariance direction")
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
        if path_side > 0 else (event["high"] - event["close"]) / candle_range
    )
    if location < float(c["EVENT_CLOSE_FRACTION"]):
        return _wait(f"Event close lacks directional control ({location:.3f})")

    trade_side = -path_side if bool(c["FADE_DOMINANCE"]) else path_side
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
    tp = (
        math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
        if trade_side > 0 else math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    )
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": (
            f"S403 {signal} Semivariance "
            f"{'Exhaustion Fade' if bool(c['FADE_DOMINANCE']) else 'Continuation'} "
            f"{rr:g}R"
        ),
        "reason": (
            f"dominance={recent_dominance:.4f}, baseline={baseline_dominance:.4f}, "
            f"ratio={dominance_ratio:.4f}, rise={dominance_rise:.4f}, "
            f"energy_atr2={energy_atr2:.4f}, path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
