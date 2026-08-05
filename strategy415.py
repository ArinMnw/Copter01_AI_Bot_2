# -*- coding: utf-8 -*-
"""S415 — Conditional Direction-Entropy Release 7R.

S415 models closed candle directions as a first-order two-state Markov chain.
It looks for recent conditional entropy below disjoint baseline blocks, then
uses the transition probability conditioned on the fully closed event candle
to choose the next-bar side.  Entropy compression is a proxy for temporary
order-flow sequencing rather than volatility magnitude.  Entry is next-open,
with an event-extreme ATR stop and a target of at least 7R.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 24,
    "ENTROPY_RATIO_MAX": 0.92,
    "ENTROPY_DROP_MIN": 0.04,
    "FORECAST_EDGE_MIN": 0.08,
    "INVERT_FORECAST": False,
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
    "TP_RR": 7.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _binary_entropy(probability):
    if probability <= 0.0 or probability >= 1.0:
        return 0.0
    return -(probability * math.log2(probability)
             + (1.0 - probability) * math.log2(1.0 - probability))


def _transition_metrics(bars):
    signs = []
    for bar in bars:
        body = bar["close"] - bar["open"]
        if body > 0.0:
            signs.append(1)
        elif body < 0.0:
            signs.append(-1)
    if len(signs) < 12:
        return None
    counts = {(1, 1): 0, (1, -1): 0, (-1, 1): 0, (-1, -1): 0}
    for previous, current in zip(signs, signs[1:]):
        counts[(previous, current)] += 1
    up_origin = counts[(1, 1)] + counts[(1, -1)]
    down_origin = counts[(-1, 1)] + counts[(-1, -1)]
    total = up_origin + down_origin
    if total <= 0:
        return None
    p_up_after_up = (counts[(1, 1)] + 1.0) / (up_origin + 2.0)
    p_up_after_down = (counts[(-1, 1)] + 1.0) / (down_origin + 2.0)
    entropy = (
        up_origin * _binary_entropy(p_up_after_up)
        + down_origin * _binary_entropy(p_up_after_down)
    ) / total
    return {
        "entropy": entropy,
        "p_up_after_up": p_up_after_up,
        "p_up_after_down": p_up_after_down,
    }


def detect_s415(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S415 payload using closed bars only."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        ratio_max = float(c["ENTROPY_RATIO_MAX"])
        drop_min = float(c["ENTROPY_DROP_MIN"])
        edge_min = float(c["FORECAST_EDGE_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: entropy windows are inconsistent")
    if not all(math.isfinite(value) and value >= 0.0
               for value in (ratio_max, drop_min, edge_min)):
        return _wait("Invalid config: entropy gates are invalid")
    if ratio_max > 1.5 or edge_min >= 0.5:
        return _wait("Invalid config: entropy or forecast gate is out of range")
    if not 0 <= start_hour < end_hour <= 24:
        return _wait("Invalid config: session hours are invalid")
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
            _transition_metrics(baseline[index:index + recent_count])
            for index in range(0, len(baseline), recent_count)
        ]
        recent_metrics = _transition_metrics(recent)
        if recent_metrics is None or any(item is None for item in baseline_metrics):
            return _wait("Conditional direction entropy is unavailable")
        baseline_entropy = statistics.median(
            item["entropy"] for item in baseline_metrics
        )
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if baseline_entropy <= 0.0 or atr <= 0.0:
        return _wait("Entropy baseline or ATR is unavailable")
    entropy = recent_metrics["entropy"]
    entropy_ratio = entropy / baseline_entropy
    entropy_drop = baseline_entropy - entropy
    if entropy_ratio > ratio_max:
        return _wait(f"Conditional entropy is not compressed ({entropy_ratio:.3f})")
    if entropy_drop < drop_min:
        return _wait(f"Conditional entropy drop is weak ({entropy_drop:.3f})")

    event_body = event["close"] - event["open"]
    event_range = event["high"] - event["low"]
    if event_body == 0.0 or event_range <= 0.0:
        return _wait("Event candle has no directional state")
    event_side = 1 if event_body > 0.0 else -1
    p_up = (recent_metrics["p_up_after_up"] if event_side > 0
            else recent_metrics["p_up_after_down"])
    forecast_edge = abs(p_up - 0.5)
    if forecast_edge < edge_min:
        return _wait(f"Transition forecast is weak ({forecast_edge:.3f})")
    forecast_side = 1 if p_up > 0.5 else -1
    trade_side = -forecast_side if bool(c["INVERT_FORECAST"]) else forecast_side

    median_volume = statistics.median(float(bar["tick_volume"]) for bar in recent)
    if median_volume <= 0.0:
        return _wait("Recent volume is unavailable")
    volume_ratio = event["tick_volume"] / median_volume
    if volume_ratio < float(c["EVENT_VOLUME_RATIO_MIN"]):
        return _wait(f"Event participation is weak ({volume_ratio:.3f}x)")
    if abs(event_body) < atr * float(c["EVENT_BODY_ATR_MIN"]):
        return _wait("Event body is too small versus ATR")
    if event_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Event range is too small versus ATR")
    if abs(event_body) / event_range < float(c["EVENT_BODY_FRACTION_MIN"]):
        return _wait("Event lacks directional body control")
    event_location = ((event["close"] - event["low"]) / event_range
                      if event_side > 0 else
                      (event["high"] - event["close"]) / event_range)
    if event_location < float(c["EVENT_CLOSE_FRACTION"]):
        return _wait(f"Event close lacks state control ({event_location:.3f})")

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
          if trade_side > 0 else
          math.floor((raw_tp + 1e-12) * 100.0) / 100.0)
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S415 {signal} Transition-Entropy {rr:g}R",
        "reason": (
            f"entropy={entropy:.4f}, baseline={baseline_entropy:.4f}, "
            f"ratio={entropy_ratio:.4f}, p_up={p_up:.4f}, "
            f"forecast_edge={forecast_edge:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
