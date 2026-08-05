# -*- coding: utf-8 -*-
"""S389 — Signed-Flow Lead-Lag Release 11R.

Tick volume signed by candle direction is used as a causal order-flow proxy.
The strategy estimates whether pressure on bar t-1 predicts the return on bar
t, and requires that recent lag-one correlation is positive, stronger than its
older baseline.  The lag construction itself isolates predictive information
from the same-bar volume/price identity.  A coherent
recent path and a closed release candle determine direction and dynamic risk.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 80,
    "RECENT_BARS": 24,
    "LEAD_CORR_MIN": 0.195,
    "LEAD_CORR_RISE_MIN": 0.15,
    "LEAD_ADVANTAGE_MIN": -1.00,
    "DIRECTIONAL_FLOW_MIN": 0.10,
    "PATH_EFFICIENCY_MIN": 0.15,
    "NET_MOVE_ATR_MIN": 0.35,
    "EVENT_VOLUME_RATIO_MIN": 1.10,
    "EVENT_BODY_ATR_MIN": 0.65,
    "EVENT_RANGE_ATR_MIN": 0.70,
    "EVENT_BODY_FRACTION_MIN": 0.72,
    "EVENT_CLOSE_FRACTION": 0.75,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.25,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 11.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _pearson(left, right):
    if len(left) != len(right) or len(left) < 3:
        return None
    mean_left = statistics.fmean(left)
    mean_right = statistics.fmean(right)
    centered_left = [value - mean_left for value in left]
    centered_right = [value - mean_right for value in right]
    variance_left = sum(value * value for value in centered_left)
    variance_right = sum(value * value for value in centered_right)
    denominator = math.sqrt(variance_left * variance_right)
    if denominator <= 0.0:
        return None
    return sum(a * b for a, b in zip(centered_left, centered_right)) / denominator


def _flow_features(bars):
    pressure = []
    returns = []
    travelled = 0.0
    for index, bar in enumerate(bars):
        body = bar["close"] - bar["open"]
        sign = 1.0 if body > 0.0 else -1.0 if body < 0.0 else 0.0
        pressure.append(sign * bar["tick_volume"])
        if index:
            change = bar["close"] - bars[index - 1]["close"]
            returns.append(change)
            travelled += abs(change)
    lead = _pearson(pressure[:-1], returns)
    contemporaneous = _pearson(pressure[1:], returns)
    return pressure, lead, contemporaneous, travelled


def detect_s389(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S389 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(10, int(c["RECENT_BARS"]))
        lead_min = float(c["LEAD_CORR_MIN"])
        rise_min = float(c["LEAD_CORR_RISE_MIN"])
        advantage_min = float(c["LEAD_ADVANTAGE_MIN"])
        directional_min = float(c["DIRECTIONAL_FLOW_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_move_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (
            directional_min, path_min, net_move_min,
        )
    ) or not math.isfinite(lead_min) or not math.isfinite(rise_min) or not math.isfinite(advantage_min):
        return _wait("Invalid config: lead-lag gates are invalid")
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
        _, baseline_lead, _, _ = _flow_features(baseline)
        pressure, recent_lead, contemporaneous, travelled = _flow_features(recent)
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
    if atr <= 0.0 or travelled <= 0.0:
        return _wait("ATR or recent path is zero")
    if baseline_lead is None or recent_lead is None or contemporaneous is None:
        return _wait("Lead-lag correlation is unavailable")
    lead_rise = recent_lead - baseline_lead
    lead_advantage = recent_lead - contemporaneous
    if recent_lead < lead_min:
        return _wait(f"Recent signed-flow lead is weak ({recent_lead:.3f})")
    if lead_rise < rise_min:
        return _wait(f"Signed-flow lead has not risen enough ({lead_rise:.3f})")
    if advantage_min > -1.0 and lead_advantage < advantage_min:
        return _wait(f"Lead does not exceed same-bar correlation ({lead_advantage:.3f})")

    total_volume = sum(abs(value) for value in pressure)
    if total_volume <= 0.0:
        return _wait("Recent signed-flow volume is zero")
    directional_flow = sum(pressure) / total_volume
    if abs(directional_flow) < directional_min:
        return _wait(f"Directional flow is weak ({directional_flow:.3f})")
    net_move = recent[-1]["close"] - recent[0]["close"]
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Auction path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Auction net move is too small versus ATR")
    side = 1 if directional_flow > 0.0 else -1
    if side * net_move <= 0.0:
        return _wait("Signed flow and net move disagree")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or side * body <= 0.0:
        return _wait("Event does not align with predictive signed flow")
    median_volume = statistics.median(abs(value) for value in pressure)
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
        "pattern": f"S389 {signal} Signed-Flow Lead-Lag Release {rr:g}R",
        "reason": (
            f"lead={recent_lead:.4f}, baseline={baseline_lead:.4f}, "
            f"rise={lead_rise:.4f}, same-bar={contemporaneous:.4f}, "
            f"advantage={lead_advantage:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
