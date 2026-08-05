# -*- coding: utf-8 -*-
"""S414 — Volume-Normalized Price-Impact Release 7R.

The strategy compares recent candle displacement per square-root tick volume
with disjoint baseline blocks.  Rising price impact accompanied by directional
signed-volume imbalance is a bar-data proxy for thinning opposing liquidity.
It enters only after a participated closed confirmation bar.  Market fills are
simulated at next-open with an event-extreme ATR stop and a target of >=7R.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 24,
    "IMPACT_RATIO_MIN": 1.15,
    "IMPACT_RISE_MIN": 0.05,
    "FLOW_IMBALANCE_MIN": 0.15,
    "PATH_EFFICIENCY_MIN": 0.12,
    "NET_MOVE_ATR_MIN": 0.35,
    "REQUIRE_PATH_ALIGNMENT": True,
    "FADE_FLOW": True,
    "EVENT_VOLUME_RATIO_MIN": 1.00,
    "EVENT_BODY_ATR_MIN": 0.65,
    "EVENT_RANGE_ATR_MIN": 0.65,
    "EVENT_BODY_FRACTION_MIN": 0.60,
    "EVENT_CLOSE_FRACTION": 0.70,
    "SESSION_START_HOUR": 7,
    "SESSION_END_HOUR": 15,
    "SL_BUFFER_ATR": 0.18,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": False,
    "TP_RR": 8.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _impact_metrics(bars):
    impacts = []
    signed_flow = 0.0
    total_flow = 0.0
    for bar in bars:
        volume = float(bar["tick_volume"])
        open_price = bar["open"]
        close = bar["close"]
        if volume <= 0.0 or min(open_price, close) <= 0.0:
            return None
        move = math.log(close / open_price)
        root_volume = math.sqrt(volume)
        impacts.append(abs(move) / root_volume)
        if move > 0.0:
            signed_flow += root_volume
        elif move < 0.0:
            signed_flow -= root_volume
        total_flow += root_volume
    if not impacts or total_flow <= 0.0:
        return None
    return {
        "impact": statistics.median(impacts),
        "imbalance": signed_flow / total_flow,
    }


def detect_s414(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S414 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        ratio_min = float(c["IMPACT_RATIO_MIN"])
        rise_min = float(c["IMPACT_RISE_MIN"])
        imbalance_min = float(c["FLOW_IMBALANCE_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: impact windows are inconsistent")
    gates = (ratio_min, rise_min, imbalance_min, path_min, net_min)
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: impact gates are invalid")
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
            _impact_metrics(baseline[index:index + recent_count])
            for index in range(0, len(baseline), recent_count)
        ]
        recent_metrics = _impact_metrics(recent)
        if recent_metrics is None or any(item is None for item in baseline_metrics):
            return _wait("Price-impact metric is unavailable")
        baseline_impact = statistics.median(
            item["impact"] for item in baseline_metrics
        )
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if baseline_impact <= 0.0 or atr <= 0.0:
        return _wait("Impact baseline or ATR is unavailable")
    impact = recent_metrics["impact"]
    impact_ratio = impact / baseline_impact
    impact_rise = impact_ratio - 1.0
    if impact_ratio < ratio_min:
        return _wait(f"Price-impact ratio is weak ({impact_ratio:.3f})")
    if impact_rise < rise_min:
        return _wait(f"Price-impact rise is weak ({impact_rise:.3f})")
    imbalance = recent_metrics["imbalance"]
    if abs(imbalance) < imbalance_min:
        return _wait(f"Signed-flow imbalance is weak ({imbalance:.3f})")
    flow_side = 1 if imbalance > 0.0 else -1
    trade_side = -flow_side if bool(c["FADE_FLOW"]) else flow_side

    returns = [recent[index]["close"] - recent[index - 1]["close"]
               for index in range(1, len(recent))]
    travelled = sum(abs(value) for value in returns)
    net_move = recent[-1]["close"] - recent[0]["close"]
    if travelled <= 0.0 or net_move == 0.0:
        return _wait("Recent price path is unavailable")
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Impact path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_min:
        return _wait("Impact displacement is too small versus ATR")
    if bool(c["REQUIRE_PATH_ALIGNMENT"]) and flow_side * net_move <= 0.0:
        return _wait("Price path disagrees with signed-flow imbalance")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or trade_side * body <= 0.0:
        return _wait("Event direction does not confirm liquidity release")
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
        "pattern": f"S414 {signal} Price-Impact Fade {rr:g}R",
        "reason": (
            f"impact={impact:.8f}, baseline={baseline_impact:.8f}, "
            f"ratio={impact_ratio:.4f}, imbalance={imbalance:.4f}, "
            f"path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
