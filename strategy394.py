# -*- coding: utf-8 -*-
"""S394 — Variance-Ratio Serial-Dependence Release 10R.

The strategy applies an overlapping Lo-MacKinlay-style variance ratio to close
returns.  A multi-bar variance materially above q times one-bar variance
indicates positive serial dependence rather than a random walk.  Recent serial
dependence must strengthen versus an older baseline, while net displacement,
path efficiency, and a closed release candle determine direction.  Execution
uses next-open market fills and an event-extreme plus ATR stop.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 80,
    "RECENT_BARS": 28,
    "VR_HORIZON": 3,
    "VARIANCE_RATIO_MIN": 1.15,
    "VARIANCE_RATIO_RISE_MIN": 0.10,
    "PATH_EFFICIENCY_MIN": 0.18,
    "NET_MOVE_ATR_MIN": 0.40,
    "EVENT_VOLUME_RATIO_MIN": 1.05,
    "EVENT_BODY_ATR_MIN": 0.65,
    "EVENT_RANGE_ATR_MIN": 0.75,
    "EVENT_BODY_FRACTION_MIN": 0.72,
    "EVENT_CLOSE_FRACTION": 0.75,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.225,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 10.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _population_variance(values):
    if len(values) < 2:
        return None
    mean = statistics.fmean(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _variance_ratio(bars, horizon):
    returns = [
        bars[index]["close"] - bars[index - 1]["close"]
        for index in range(1, len(bars))
    ]
    if len(returns) < horizon + 2:
        return None, 0.0
    one_variance = _population_variance(returns)
    aggregate = [
        sum(returns[index:index + horizon])
        for index in range(len(returns) - horizon + 1)
    ]
    aggregate_variance = _population_variance(aggregate)
    if one_variance is None or aggregate_variance is None or one_variance <= 0.0:
        return None, 0.0
    travelled = sum(abs(value) for value in returns)
    return aggregate_variance / (horizon * one_variance), travelled


def detect_s394(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S394 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        horizon = max(2, int(c["VR_HORIZON"]))
        ratio_min = float(c["VARIANCE_RATIO_MIN"])
        ratio_rise_min = float(c["VARIANCE_RATIO_RISE_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_move_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or horizon >= recent_count // 2:
        return _wait("Invalid config: variance-ratio windows are inconsistent")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (ratio_min, ratio_rise_min, path_min, net_move_min)
    ):
        return _wait("Invalid config: variance-ratio gates are invalid")
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
        baseline_ratio, _ = _variance_ratio(baseline, horizon)
        recent_ratio, travelled = _variance_ratio(recent, horizon)
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
    if baseline_ratio is None or recent_ratio is None or atr <= 0.0:
        return _wait("Variance ratio or ATR is unavailable")
    ratio_rise = recent_ratio - baseline_ratio
    if recent_ratio < ratio_min:
        return _wait(f"Recent variance ratio is weak ({recent_ratio:.3f})")
    if ratio_rise < ratio_rise_min:
        return _wait(f"Variance ratio has not risen enough ({ratio_rise:.3f})")
    if travelled <= 0.0:
        return _wait("Recent path is zero")
    net_move = recent[-1]["close"] - recent[0]["close"]
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Auction path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Net move is too small versus ATR")
    side = 1 if net_move > 0.0 else -1

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or side * body <= 0.0:
        return _wait("Event does not confirm serial-dependence direction")
    median_volume = statistics.median(
        float(bar["tick_volume"]) for bar in recent
    )
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
        "pattern": f"S394 {signal} Variance-Ratio Serial Dependence {rr:g}R",
        "reason": (
            f"vr{horizon}={recent_ratio:.4f}, baseline={baseline_ratio:.4f}, "
            f"rise={ratio_rise:.4f}, path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
