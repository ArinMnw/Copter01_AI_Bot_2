# -*- coding: utf-8 -*-
"""S404 — Amihud Illiquidity-Shock Reversal 7R.

Absolute closed return per unit of tick volume is a price-impact proxy.  S404
normalizes this proxy inside each block, compares the recent upper quartile
with disjoint baseline blocks, and identifies the signed direction of the
illiquid impulse.  A fully closed participated candle must reverse that impulse
before entry, creating timing distinct from release-continuation strategies.
The market order fills next-open, with an event-extreme stop and >=7R target.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 24,
    "IMPACT_QUANTILE": 0.65,
    "IMPACT_RATIO_MIN": 1.15,
    "IMPACT_RISE_ATR_MIN": 0.01,
    "TOP_IMPULSE_ATR_MIN": 0.30,
    "SIGNED_IMPULSE_ATR_MIN": 0.08,
    "PATH_EFFICIENCY_MIN": 0.08,
    "EVENT_VOLUME_RATIO_MIN": 1.00,
    "EVENT_BODY_ATR_MIN": 0.45,
    "EVENT_RANGE_ATR_MIN": 0.65,
    "EVENT_BODY_FRACTION_MIN": 0.60,
    "EVENT_CLOSE_FRACTION": 0.70,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.18,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "REQUIRE_REVERSAL": True,
    "TP_RR": 8.0,
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


def _impact_metrics(bars, quantile):
    if len(bars) < 9:
        return None
    median_volume = statistics.median(float(bar["tick_volume"]) for bar in bars)
    if median_volume <= 0.0:
        return None
    returns = []
    impacts = []
    for index in range(1, len(bars)):
        value = bars[index]["close"] - bars[index - 1]["close"]
        volume = max(float(bars[index]["tick_volume"]), 1.0)
        returns.append(value)
        impacts.append(abs(value) * median_volume / volume)
    total_impact = sum(impacts)
    if total_impact <= 0.0 or not math.isfinite(total_impact):
        return None
    signed = sum(value * impact for value, impact in zip(returns, impacts)) / total_impact
    return {
        "score": _linear_quantile(impacts, quantile),
        "signed": signed,
        "top_return": max(abs(value) for value in returns),
        "returns": returns,
    }


def detect_s404(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S404 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        quantile = float(c["IMPACT_QUANTILE"])
        ratio_min = float(c["IMPACT_RATIO_MIN"])
        rise_min = float(c["IMPACT_RISE_ATR_MIN"])
        top_min = float(c["TOP_IMPULSE_ATR_MIN"])
        signed_min = float(c["SIGNED_IMPULSE_ATR_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: impact windows are inconsistent")
    gates = (ratio_min, rise_min, top_min, signed_min, path_min)
    if not 0.50 <= quantile <= 0.95:
        return _wait("Invalid config: impact quantile is invalid")
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: impact gates are invalid")
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
            _impact_metrics(baseline[index:index + recent_count], quantile)
            for index in range(0, len(baseline), recent_count)
        ]
        recent_metrics = _impact_metrics(recent, quantile)
        if recent_metrics is None or any(
            metrics is None for metrics in baseline_metrics
        ):
            return _wait("Price impact is unavailable")
        baseline_score = statistics.median(
            metrics["score"] for metrics in baseline_metrics
        )
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if baseline_score <= 0.0 or atr <= 0.0:
        return _wait("Impact baseline or ATR is unavailable")
    impact_score = recent_metrics["score"]
    impact_ratio = impact_score / baseline_score
    impact_rise_atr = (impact_score - baseline_score) / atr
    if impact_ratio < ratio_min:
        return _wait(f"Impact ratio is weak ({impact_ratio:.3f})")
    if impact_rise_atr < rise_min:
        return _wait(f"Impact rise is weak ({impact_rise_atr:.3f} ATR)")
    if recent_metrics["top_return"] < atr * top_min:
        return _wait("Top illiquid impulse is too small")
    signed_impulse = recent_metrics["signed"]
    if abs(signed_impulse) < atr * signed_min:
        return _wait("Signed impact is too small versus ATR")
    impulse_side = 1 if signed_impulse > 0.0 else -1
    recent_returns = recent_metrics["returns"]
    travelled = sum(abs(value) for value in recent_returns)
    net_move = recent[-1]["close"] - recent[0]["close"]
    if travelled <= 0.0 or net_move == 0.0:
        return _wait("Recent path is unavailable")
    net_side = 1 if net_move > 0.0 else -1
    if net_side != impulse_side:
        return _wait("Net path disagrees with signed impact")
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Auction path is inefficient ({path_efficiency:.3f})")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0:
        return _wait("Event candle is invalid")
    event_side = 1 if body > 0.0 else -1
    required_side = -impulse_side if bool(c["REQUIRE_REVERSAL"]) else impulse_side
    if event_side != required_side:
        return _wait("Event direction does not confirm impact setup")
    median_volume = statistics.median(float(bar["tick_volume"]) for bar in recent)
    volume_ratio = event["tick_volume"] / median_volume
    if volume_ratio < float(c["EVENT_VOLUME_RATIO_MIN"]):
        return _wait(f"Event participation is weak ({volume_ratio:.3f}x)")
    if abs(body) < atr * float(c["EVENT_BODY_ATR_MIN"]):
        return _wait("Event body is too small versus ATR")
    if candle_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Event range is too small versus ATR")
    if abs(body) / candle_range < float(c["EVENT_BODY_FRACTION_MIN"]):
        return _wait("Event lacks body control")
    location = (
        (event["close"] - event["low"]) / candle_range
        if event_side > 0 else (event["high"] - event["close"]) / candle_range
    )
    if location < float(c["EVENT_CLOSE_FRACTION"]):
        return _wait(f"Event close lacks directional control ({location:.3f})")

    signal = "BUY" if event_side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(event["close"], 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if event_side > 0:
        sl = math.floor((event["low"] - sl_buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + sl_buffer - 1e-12) * 100.0) / 100.0
    risk = event_side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Event risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Event risk too large versus price")
    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + event_side * rr * risk
    tp = (
        math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
        if event_side > 0 else math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    )
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": (
            f"S404 {signal} Amihud Impact "
            f"{'Reversal' if bool(c['REQUIRE_REVERSAL']) else 'Continuation'} {rr:g}R"
        ),
        "reason": (
            f"impact={impact_score:.4f}, baseline={baseline_score:.4f}, "
            f"ratio={impact_ratio:.4f}, rise_atr={impact_rise_atr:.4f}, "
            f"signed_atr={signed_impulse / atr:.4f}, path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
