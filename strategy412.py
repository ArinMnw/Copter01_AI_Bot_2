# -*- coding: utf-8 -*-
"""S412 — Consecutive-Range IoU Auction-Displacement Release 7R.

Intersection-over-union of adjacent candle ranges measures how much auction
territory is reused from one closed bar to the next.  A fall in recent median
IoU versus disjoint baseline blocks signals directional price discovery rather
than merely larger volatility.  S412 trades a participated confirming event
next-open with an event-extreme ATR stop and a target of at least 7R.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 24,
    "OVERLAP_RATIO_MAX": 0.85,
    "OVERLAP_DROP_MIN": 0.04,
    "EXPAND_OVERLAP": False,
    "OVERLAP_EXPANSION_RATIO_MIN": 1.15,
    "PATH_EFFICIENCY_MIN": 0.12,
    "NET_MOVE_ATR_MIN": 0.30,
    "FADE_PATH": False,
    "EVENT_VOLUME_RATIO_MIN": 1.00,
    "EVENT_BODY_ATR_MIN": 0.45,
    "EVENT_RANGE_ATR_MIN": 0.65,
    "EVENT_BODY_FRACTION_MIN": 0.60,
    "EVENT_CLOSE_FRACTION": 0.70,
    "SESSION_START_HOUR": 0,
    "SESSION_END_HOUR": 7,
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


def _range_iou(first, second):
    intersection = max(
        0.0,
        min(first["high"], second["high"])
        - max(first["low"], second["low"]),
    )
    union = max(first["high"], second["high"]) - min(
        first["low"], second["low"]
    )
    if union <= 0.0:
        return None
    return intersection / union


def _overlap_score(bars):
    values = [_range_iou(bars[index - 1], bars[index])
              for index in range(1, len(bars))]
    if any(value is None for value in values) or not values:
        return None
    return statistics.median(values)


def detect_s412(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S412 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        ratio_max = float(c["OVERLAP_RATIO_MAX"])
        drop_min = float(c["OVERLAP_DROP_MIN"])
        expansion_min = float(c["OVERLAP_EXPANSION_RATIO_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: overlap windows are inconsistent")
    gates = (ratio_max, drop_min, expansion_min, path_min, net_min)
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: overlap gates are invalid")
    required = max(period + 3, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured overnight window")
    try:
        bars = _bars(rates[-required:])
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        segment_count = baseline_count // recent_count
        baseline = baseline[-segment_count * recent_count:]
        baseline_scores = [
            _overlap_score(baseline[index:index + recent_count])
            for index in range(0, len(baseline), recent_count)
        ]
        recent_score = _overlap_score(recent)
        if recent_score is None or any(score is None for score in baseline_scores):
            return _wait("Range IoU is unavailable")
        baseline_score = statistics.median(baseline_scores)
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if baseline_score <= 0.0 or atr <= 0.0:
        return _wait("Overlap baseline or ATR is unavailable")
    overlap_ratio = recent_score / baseline_score
    overlap_drop = baseline_score - recent_score
    expand = bool(c["EXPAND_OVERLAP"])
    if expand:
        if overlap_ratio < expansion_min:
            return _wait(f"Overlap expansion is weak ({overlap_ratio:.3f})")
    else:
        if overlap_ratio > ratio_max:
            return _wait(f"Overlap contraction is weak ({overlap_ratio:.3f})")
        if overlap_drop < drop_min:
            return _wait(f"Overlap drop is weak ({overlap_drop:.3f})")

    returns = [recent[index]["close"] - recent[index - 1]["close"]
               for index in range(1, len(recent))]
    travelled = sum(abs(value) for value in returns)
    net_move = recent[-1]["close"] - recent[0]["close"]
    if travelled <= 0.0 or net_move == 0.0:
        return _wait("Recent path is unavailable")
    path_side = 1 if net_move > 0.0 else -1
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Auction path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_min:
        return _wait("Auction displacement is too small versus ATR")
    trade_side = -path_side if bool(c["FADE_PATH"]) else path_side

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or trade_side * body <= 0.0:
        return _wait("Event direction does not confirm overlap setup")
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
        "pattern": f"S412 {signal} Range-IoU Displacement {rr:g}R",
        "reason": (
            f"iou={recent_score:.4f}, baseline={baseline_score:.4f}, "
            f"ratio={overlap_ratio:.4f}, drop={overlap_drop:.4f}, "
            f"path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
