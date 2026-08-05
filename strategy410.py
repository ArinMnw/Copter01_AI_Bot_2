# -*- coding: utf-8 -*-
"""S410 — Rousseeuw–Croux Sn/Qn Shape-Dislocation Release 7R.

Sn is the median of each observation's median distance to all others, whereas
Qn uses the lower quartile of every pairwise distance.  Their ratio therefore
describes robust distribution shape rather than raw volatility alone.  S410
requires recent Sn/Qn shape to move above disjoint baseline blocks together
with sufficient Sn scale, then follows an efficient path after a closed event.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait
from strategy401 import _qn_scale, _returns


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 24,
    "SHAPE_RATIO_MIN": 1.04,
    "SHAPE_RISE_MIN": 0.03,
    "SN_SCALE_RATIO_MIN": 1.00,
    "SN_RISE_ATR_MIN": 0.00,
    "CONTRACT_SHAPE": False,
    "PATH_EFFICIENCY_MIN": 0.12,
    "NET_MOVE_ATR_MIN": 0.35,
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
    "FADE_PATH": False,
    "TP_RR": 7.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _sn_scale(values):
    if len(values) < 8:
        return None
    local_medians = [
        statistics.median(abs(value - other) for other in values)
        for value in values
    ]
    scale = 1.1926 * statistics.median(local_medians)
    return scale if math.isfinite(scale) and scale > 0.0 else None


def _shape_metrics(bars):
    values = _returns(bars)
    sn = _sn_scale(values)
    qn = _qn_scale(values)
    if sn is None or qn is None or qn <= 0.0:
        return None
    return {"sn": sn, "qn": qn, "shape": sn / qn, "returns": values}


def detect_s410(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S410 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        shape_ratio_min = float(c["SHAPE_RATIO_MIN"])
        shape_rise_min = float(c["SHAPE_RISE_MIN"])
        sn_ratio_min = float(c["SN_SCALE_RATIO_MIN"])
        sn_rise_min = float(c["SN_RISE_ATR_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: robust-shape windows are inconsistent")
    gates = (shape_ratio_min, shape_rise_min, sn_ratio_min, sn_rise_min,
             path_min, net_min)
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: robust-shape gates are invalid")
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
            _shape_metrics(baseline[index:index + recent_count])
            for index in range(0, len(baseline), recent_count)
        ]
        recent_metrics = _shape_metrics(recent)
        if recent_metrics is None or any(item is None for item in baseline_metrics):
            return _wait("Sn/Qn robust shape is unavailable")
        baseline_shape = statistics.median(item["shape"]
                                           for item in baseline_metrics)
        baseline_sn = statistics.median(item["sn"] for item in baseline_metrics)
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if baseline_shape <= 0.0 or baseline_sn <= 0.0 or atr <= 0.0:
        return _wait("Robust-shape baseline or ATR is unavailable")
    shape = recent_metrics["shape"]
    contract = bool(c["CONTRACT_SHAPE"])
    if contract:
        shape_ratio = baseline_shape / shape
        shape_rise = baseline_shape - shape
    else:
        shape_ratio = shape / baseline_shape
        shape_rise = shape - baseline_shape
    if shape_ratio < shape_ratio_min:
        return _wait(f"Robust-shape ratio is weak ({shape_ratio:.3f})")
    if shape_rise < shape_rise_min:
        return _wait(f"Robust-shape displacement is weak ({shape_rise:.3f})")
    sn_ratio = recent_metrics["sn"] / baseline_sn
    sn_rise_atr = (recent_metrics["sn"] - baseline_sn) / atr
    if sn_ratio < sn_ratio_min:
        return _wait(f"Sn scale ratio is weak ({sn_ratio:.3f})")
    if sn_rise_atr < sn_rise_min:
        return _wait(f"Sn scale rise is weak ({sn_rise_atr:.3f} ATR)")

    recent_returns = recent_metrics["returns"]
    travelled = sum(abs(value) for value in recent_returns)
    net_move = recent[-1]["close"] - recent[0]["close"]
    if travelled <= 0.0 or net_move == 0.0:
        return _wait("Recent path is unavailable")
    path_side = 1 if net_move > 0.0 else -1
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Robust-shape path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_min:
        return _wait("Robust-shape move is too small versus ATR")
    trade_side = -path_side if bool(c["FADE_PATH"]) else path_side

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or trade_side * body <= 0.0:
        return _wait("Event direction does not confirm robust-shape setup")
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
        "pattern": (
            f"S410 {signal} Sn-Qn Shape "
            f"{'Contraction' if contract else 'Expansion'} {rr:g}R"
        ),
        "reason": (
            f"shape={shape:.4f}, baseline={baseline_shape:.4f}, "
            f"ratio={shape_ratio:.4f}, displacement={shape_rise:.4f}, "
            f"sn_ratio={sn_ratio:.4f}, sn_rise_atr={sn_rise_atr:.4f}, "
            f"path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
