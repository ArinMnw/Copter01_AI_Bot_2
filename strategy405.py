# -*- coding: utf-8 -*-
"""S405 — Lo–MacKinlay Variance-Ratio Excursion Reversal 7R.

The overlapping q-period variance ratio compares aggregated-return variance
with q times one-period variance.  Values below one indicate negative serial
correlation and a mean-reverting auction.  S405 requires the recent ratio to
contract below disjoint baseline blocks, then waits for a fully closed reversal
candle against the recent excursion.  It enters next-open with an event-extreme
ATR stop and a target of at least 7R, using only closed bars.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 24,
    "VR_HORIZON": 4,
    "VR_MAX": 0.95,
    "VR_BASELINE_RATIO_MIN": 1.05,
    "VR_DROP_MIN": 0.08,
    "PATH_EFFICIENCY_MIN": 0.08,
    "NET_MOVE_ATR_MIN": 0.28,
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
    "TP_RR": 7.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _returns(bars):
    return [
        bars[index]["close"] - bars[index - 1]["close"]
        for index in range(1, len(bars))
    ]


def _variance_ratio(values, horizon):
    if len(values) < max(10, horizon * 3):
        return None
    one_variance = statistics.pvariance(values)
    if one_variance <= 0.0 or not math.isfinite(one_variance):
        return None
    aggregated = [
        sum(values[index:index + horizon])
        for index in range(len(values) - horizon + 1)
    ]
    ratio = statistics.pvariance(aggregated) / (horizon * one_variance)
    return ratio if math.isfinite(ratio) and ratio >= 0.0 else None


def detect_s405(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S405 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        horizon = max(2, int(c["VR_HORIZON"]))
        vr_max = float(c["VR_MAX"])
        ratio_min = float(c["VR_BASELINE_RATIO_MIN"])
        drop_min = float(c["VR_DROP_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_move_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: variance-ratio windows are inconsistent")
    if horizon * 3 > recent_count - 1:
        return _wait("Invalid config: VR horizon is too long")
    gates = (vr_max, ratio_min, drop_min, path_min, net_move_min)
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
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
        segment_count = baseline_count // recent_count
        baseline = baseline[-segment_count * recent_count:]
        baseline_ratios = [
            _variance_ratio(_returns(baseline[index:index + recent_count]), horizon)
            for index in range(0, len(baseline), recent_count)
        ]
        recent_returns = _returns(recent)
        recent_ratio = _variance_ratio(recent_returns, horizon)
        if recent_ratio is None or any(value is None for value in baseline_ratios):
            return _wait("Variance ratio is unavailable")
        baseline_ratio = statistics.median(baseline_ratios)
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if recent_ratio > vr_max:
        return _wait(f"Recent VR is not mean reverting ({recent_ratio:.3f})")
    contraction_ratio = baseline_ratio / max(recent_ratio, 1e-9)
    vr_drop = baseline_ratio - recent_ratio
    if contraction_ratio < ratio_min:
        return _wait(f"VR contraction ratio is weak ({contraction_ratio:.3f})")
    if vr_drop < drop_min:
        return _wait(f"VR drop is weak ({vr_drop:.3f})")

    travelled = sum(abs(value) for value in recent_returns)
    net_move = recent[-1]["close"] - recent[0]["close"]
    if travelled <= 0.0 or net_move == 0.0 or atr <= 0.0:
        return _wait("Recent path or ATR is unavailable")
    excursion_side = 1 if net_move > 0.0 else -1
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Auction path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Excursion is too small versus ATR")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0:
        return _wait("Event candle is invalid")
    event_side = 1 if body > 0.0 else -1
    required_side = -excursion_side if bool(c["REQUIRE_REVERSAL"]) else excursion_side
    if event_side != required_side:
        return _wait("Event direction does not confirm VR setup")
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
            f"S405 {signal} Variance Ratio "
            f"{'Reversal' if bool(c['REQUIRE_REVERSAL']) else 'Continuation'} {rr:g}R"
        ),
        "reason": (
            f"vr={recent_ratio:.4f}, baseline={baseline_ratio:.4f}, "
            f"contraction={contraction_ratio:.4f}, drop={vr_drop:.4f}, "
            f"path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
