# -*- coding: utf-8 -*-
"""S417 — Multi-Horizon Variance-Ratio Release 7R.

The variance ratio compares variance of overlapping q-bar log returns with q
times one-bar return variance.  Values above one indicate positive serial
dependence; values below one indicate mean reversion.  S417 compares the recent
ratio with disjoint baseline blocks and trades a participated closed event in
the inferred path direction (or its configured fade).  Entry is next-open with
an event-extreme ATR stop and a target of at least 7R.
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
    "CONTRACT_VR": True,
    "VR_ABS_MIN": 0.80,
    "VR_EXPANSION_RATIO_MIN": 1.15,
    "VR_RISE_MIN": 0.08,
    "VR_ABS_MAX": 1.20,
    "VR_CONTRACTION_RATIO_MAX": 0.85,
    "VR_DROP_MIN": 0.08,
    "PATH_EFFICIENCY_MIN": 0.08,
    "NET_MOVE_ATR_MIN": 0.30,
    "FADE_PATH": True,
    "EVENT_VOLUME_RATIO_MIN": 1.00,
    "EVENT_BODY_ATR_MIN": 0.45,
    "EVENT_RANGE_ATR_MIN": 0.65,
    "EVENT_BODY_FRACTION_MIN": 0.60,
    "EVENT_CLOSE_FRACTION": 0.70,
    "SESSION_START_HOUR": 0,
    "SESSION_END_HOUR": 24,
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


def _variance_ratio(bars, horizon):
    closes = [bar["close"] for bar in bars]
    if any(value <= 0.0 for value in closes):
        return None
    returns = [
        math.log(closes[index] / closes[index - 1])
        for index in range(1, len(closes))
    ]
    if len(returns) < max(10, horizon * 3):
        return None
    mean_return = sum(returns) / len(returns)
    one_variance = (
        sum(value * value for value in returns) / len(returns)
        - mean_return * mean_return
    )
    rolling = sum(returns[:horizon])
    horizon_returns = [rolling]
    for index in range(horizon, len(returns)):
        rolling += returns[index] - returns[index - horizon]
        horizon_returns.append(rolling)
    if one_variance <= 0.0 or len(horizon_returns) < 3:
        return None
    mean_horizon = sum(horizon_returns) / len(horizon_returns)
    horizon_variance = (
        sum(value * value for value in horizon_returns) / len(horizon_returns)
        - mean_horizon * mean_horizon
    )
    return horizon_variance / (horizon * one_variance)


def detect_s417(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S417 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        horizon = max(2, int(c["VR_HORIZON"]))
        absolute_min = float(c["VR_ABS_MIN"])
        expansion_min = float(c["VR_EXPANSION_RATIO_MIN"])
        rise_min = float(c["VR_RISE_MIN"])
        absolute_max = float(c["VR_ABS_MAX"])
        contraction_max = float(c["VR_CONTRACTION_RATIO_MAX"])
        drop_min = float(c["VR_DROP_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: variance-ratio windows are inconsistent")
    gates = (
        absolute_min, expansion_min, rise_min, absolute_max,
        contraction_max, drop_min, path_min, net_min,
    )
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: variance-ratio gates are invalid")
    if horizon >= recent_count // 2:
        return _wait("Invalid config: variance-ratio horizon is too large")
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
        baseline_ratios = [
            _variance_ratio(baseline[index:index + recent_count], horizon)
            for index in range(0, len(baseline), recent_count)
        ]
        recent_ratio = _variance_ratio(recent, horizon)
        if recent_ratio is None or any(value is None for value in baseline_ratios):
            return _wait("Multi-horizon variance ratio is unavailable")
        baseline_ratio = statistics.median(baseline_ratios)
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if baseline_ratio <= 0.0 or atr <= 0.0:
        return _wait("Variance-ratio baseline or ATR is unavailable")
    relative_ratio = recent_ratio / baseline_ratio
    contract = bool(c["CONTRACT_VR"])
    if contract:
        if recent_ratio > absolute_max:
            return _wait(f"Absolute variance ratio is too high ({recent_ratio:.3f})")
        if relative_ratio > contraction_max:
            return _wait(f"Variance-ratio contraction is weak ({relative_ratio:.3f})")
        if baseline_ratio - recent_ratio < drop_min:
            return _wait("Variance-ratio drop is weak")
    else:
        if recent_ratio < absolute_min:
            return _wait(f"Absolute variance ratio is weak ({recent_ratio:.3f})")
        if relative_ratio < expansion_min:
            return _wait(f"Variance-ratio expansion is weak ({relative_ratio:.3f})")
        if recent_ratio - baseline_ratio < rise_min:
            return _wait("Variance-ratio rise is weak")

    price_changes = [
        recent[index]["close"] - recent[index - 1]["close"]
        for index in range(1, len(recent))
    ]
    travelled = sum(abs(value) for value in price_changes)
    net_move = recent[-1]["close"] - recent[0]["close"]
    if travelled <= 0.0 or net_move == 0.0:
        return _wait("Recent variance-ratio path is unavailable")
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Variance-ratio path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_min:
        return _wait("Variance-ratio displacement is too small versus ATR")
    path_side = 1 if net_move > 0.0 else -1
    trade_side = -path_side if bool(c["FADE_PATH"]) else path_side

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or trade_side * body <= 0.0:
        return _wait("Event direction does not confirm variance-ratio setup")
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
                if trade_side > 0 else
                (event["high"] - event["close"]) / candle_range)
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
          if trade_side > 0 else
          math.floor((raw_tp + 1e-12) * 100.0) / 100.0)
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S417 {signal} Variance-Ratio Fade {rr:g}R",
        "reason": (
            f"vr={recent_ratio:.4f}, baseline={baseline_ratio:.4f}, "
            f"relative={relative_ratio:.4f}, path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
