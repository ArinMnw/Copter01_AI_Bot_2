# -*- coding: utf-8 -*-
"""S363 - Directional Amihud-illiquidity expansion release.

S363 estimates intraday illiquidity with absolute log return per unit of tick
volume.  A recent rise versus disjoint baseline blocks means price displacement
requires relatively little displayed activity.  Signed illiquidity pressure,
net path, and a closed release must agree before continuation entry.

All illiquidity and path inputs precede the release candle.  Entry is next-open
market, SL is beyond the closed release extreme plus ATR, and TP is at least
7R.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 80,
    "RECENT_BARS": 20,
    "ILLIQUIDITY_RATIO_MIN": 1.20,
    "DIRECTIONAL_PRESSURE_MIN": 0.20,
    "PATH_EFFICIENCY_MIN": 0.22,
    "NET_MOVE_ATR_MIN": 0.50,
    "RELEASE_BODY_ATR_MIN": 0.80,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.80,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 8.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _illiquidity_profile(bars):
    if len(bars) < 8:
        return None
    closes = [float(bar["close"]) for bar in bars]
    if not all(math.isfinite(value) and value > 0.0 for value in closes):
        return None
    signed_components = []
    for index in range(1, len(bars)):
        volume = float(bars[index].get("tick_volume", 0.0))
        if not math.isfinite(volume) or volume <= 0.0:
            continue
        log_return = math.log(closes[index] / closes[index - 1])
        signed_components.append(log_return / volume)
    if len(signed_components) < 6:
        return None
    illiquidity = sum(abs(value) for value in signed_components) / len(
        signed_components
    )
    total_pressure = sum(abs(value) for value in signed_components)
    if illiquidity <= 0.0 or total_pressure <= 0.0:
        return None
    signed_pressure = sum(signed_components) / total_pressure
    net_move = closes[-1] - closes[0]
    if abs(net_move) <= 1e-12 or abs(signed_pressure) <= 1e-12:
        return None
    side = 1 if signed_pressure > 0.0 else -1
    if net_move * side <= 0.0:
        return None
    travelled = sum(
        abs(closes[index] - closes[index - 1])
        for index in range(1, len(closes))
    )
    if travelled <= 0.0:
        return None
    path_efficiency = abs(net_move) / travelled
    return illiquidity, abs(signed_pressure), side, net_move, path_efficiency


def detect_s363(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after directional Amihud illiquidity expands."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        ratio_min = float(c["ILLIQUIDITY_RATIO_MIN"])
        pressure_min = float(c["DIRECTIONAL_PRESSURE_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not math.isfinite(ratio_min) or ratio_min <= 0.0:
        return _wait("Invalid config: illiquidity ratio is invalid")
    if not math.isfinite(pressure_min) or not 0.0 <= pressure_min <= 1.0:
        return _wait("Invalid config: directional pressure is invalid")

    required = max(period + 5, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        baseline_illiquidities = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _illiquidity_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_illiquidities.append(profile[0])
        recent_profile = _illiquidity_profile(recent)
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
    if atr <= 0.0:
        return _wait("ATR is zero")
    if recent_profile is None or not baseline_illiquidities:
        return _wait("Illiquidity profile is unavailable")

    illiquidity, pressure, side, net_move, path_efficiency = recent_profile
    baseline_illiquidity = statistics.median(baseline_illiquidities)
    if baseline_illiquidity <= 0.0:
        return _wait("Baseline illiquidity is zero")
    illiquidity_ratio = illiquidity / baseline_illiquidity
    if illiquidity_ratio < ratio_min:
        return _wait(
            f"No illiquidity expansion ({illiquidity_ratio:.3f}x)"
        )
    if pressure < pressure_min:
        return _wait(f"Directional illiquidity is weak ({pressure:.3f})")
    if path_efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Illiquid path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Illiquid path net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes illiquidity pressure")
    if abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if candle_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    close_fraction = (
        (event["close"] - event["low"]) / candle_range
        if side > 0
        else (event["high"] - event["close"]) / candle_range
    )
    if close_fraction < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Release lacks directional close control")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(event["close"], 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor(
            (event["low"] - sl_buffer + 1e-12) * 100.0
        ) / 100.0
    else:
        sl = math.ceil(
            (event["high"] + sl_buffer - 1e-12) * 100.0
        ) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Release risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Release risk too large versus price")

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
        "pattern": f"S363 {signal} Amihud Expansion {rr:g}R",
        "reason": (
            f"Amihud illiquidity={illiquidity_ratio:.4f}x, "
            f"pressure={pressure:.4f}, path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
