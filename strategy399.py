# -*- coding: utf-8 -*-
"""S399 — L-Kurtosis Tail-Weight Expansion Release 7R.

Sample probability-weighted moments produce L-kurtosis tau4 = L4/L2, a
linear-order-statistic measure of distributional tail weight.  Recent tau4
must exceed both an absolute floor and the median of disjoint baseline blocks.
Unlike L-skewness, tau4 is unsigned; net displacement and path efficiency set
direction before a participated closed release candle confirms execution.
Orders fill at the next open with an event-extreme plus ATR stop and >=7R TP.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 84,
    "RECENT_BARS": 28,
    "L_KURTOSIS_MIN": 0.10,
    "L_KURTOSIS_RISE_MIN": 0.02,
    "L_SCALE_ATR_MIN": 0.08,
    "PATH_EFFICIENCY_MIN": 0.14,
    "NET_MOVE_ATR_MIN": 0.30,
    "EVENT_VOLUME_RATIO_MIN": 1.05,
    "EVENT_BODY_ATR_MIN": 0.65,
    "EVENT_RANGE_ATR_MIN": 0.75,
    "EVENT_BODY_FRACTION_MIN": 0.72,
    "EVENT_CLOSE_FRACTION": 0.75,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.20,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 7.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _returns(bars):
    return [
        bars[index]["close"] - bars[index - 1]["close"]
        for index in range(1, len(bars))
    ]


def _l_kurtosis_profile(values):
    ordered = sorted(values)
    count = len(ordered)
    if count < 8:
        return None, 0.0
    b0 = statistics.fmean(ordered)
    b1 = sum(index * value for index, value in enumerate(ordered))
    b1 /= count * (count - 1)
    b2 = sum(
        index * (index - 1) * value
        for index, value in enumerate(ordered) if index >= 2
    )
    b2 /= count * (count - 1) * (count - 2)
    b3 = sum(
        index * (index - 1) * (index - 2) * value
        for index, value in enumerate(ordered) if index >= 3
    )
    b3 /= count * (count - 1) * (count - 2) * (count - 3)
    l2 = 2.0 * b1 - b0
    l4 = 20.0 * b3 - 30.0 * b2 + 12.0 * b1 - b0
    if l2 <= 0.0 or not math.isfinite(l2):
        return None, 0.0
    return l4 / l2, l2


def detect_s399(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S399 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        kurtosis_min = float(c["L_KURTOSIS_MIN"])
        rise_min = float(c["L_KURTOSIS_RISE_MIN"])
        scale_min = float(c["L_SCALE_ATR_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_move_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: L-kurtosis windows are inconsistent")
    gates = (kurtosis_min, rise_min, scale_min, path_min, net_move_min)
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: L-kurtosis gates are invalid")
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
        profiles = [
            _l_kurtosis_profile(_returns(baseline[index:index + recent_count]))
            for index in range(0, len(baseline), recent_count)
        ]
        recent_returns = _returns(recent)
        recent_kurtosis, recent_scale = _l_kurtosis_profile(recent_returns)
        baseline_kurtosis = statistics.median(item[0] for item in profiles)
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if recent_kurtosis is None or atr <= 0.0:
        return _wait("L-kurtosis or ATR is unavailable")
    kurtosis_rise = recent_kurtosis - baseline_kurtosis
    if recent_kurtosis < kurtosis_min:
        return _wait(f"Recent L-kurtosis is weak ({recent_kurtosis:.3f})")
    if kurtosis_rise < rise_min:
        return _wait(f"L-kurtosis has not expanded ({kurtosis_rise:.3f})")
    if recent_scale < atr * scale_min:
        return _wait("Recent L-scale is too narrow")
    travelled = sum(abs(value) for value in recent_returns)
    if travelled <= 0.0:
        return _wait("Recent path is zero")
    net_move = recent[-1]["close"] - recent[0]["close"]
    side = 1 if net_move > 0.0 else -1
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Auction path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Net move is too small versus ATR")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or side * body <= 0.0:
        return _wait("Event does not confirm tail-weight direction")
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
        if side > 0 else (event["high"] - event["close"]) / candle_range
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
        if side > 0 else math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    )
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S399 {signal} L-Kurtosis Tail-Weight Expansion {rr:g}R",
        "reason": (
            f"l_kurtosis={recent_kurtosis:.4f}, "
            f"baseline={baseline_kurtosis:.4f}, rise={kurtosis_rise:.4f}, "
            f"l_scale={recent_scale:.4f}, path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
