# -*- coding: utf-8 -*-
"""S373 — Signed Amihud Liquidity-Impact Release.

The detector looks for a directional expansion in absolute log return per
unit of tick volume.  A move that travels farther with no matching expansion
in participation can reveal a liquidity vacuum; a closed directional release
then follows that repricing with a short event-extreme stop.

Only the supplied closed bars are read.  The signal is a market-order quote;
the replay engine remains responsible for filling it at the next bar open.
"""

from __future__ import annotations

import math
import statistics


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 60,
    "RECENT_BARS": 20,
    "IMPACT_RATIO_MIN": 1.10,
    "DIRECTIONAL_IMPACT_MIN": 0.15,
    "VOLUME_RATIO_MAX": 1.15,
    "PATH_EFFICIENCY_MIN": 0.26,
    "NET_MOVE_ATR_MIN": 0.50,
    "RELEASE_BODY_ATR_MIN": 0.65,
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
    "TP_RR": 10.0,
    "BE_RR": 0.05,
    "CANCEL_BARS": 3,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite rate value")
    return number


def _bars(rates):
    result = []
    previous_time = None
    for raw in rates:
        timestamp = int(_finite(raw["time"]))
        if previous_time is not None and timestamp <= previous_time:
            raise ValueError("rates must be chronological")
        previous_time = timestamp
        bar = {
            "time": timestamp,
            "open": _finite(raw["open"]),
            "high": _finite(raw["high"]),
            "low": _finite(raw["low"]),
            "close": _finite(raw["close"]),
            "tick_volume": max(1.0, _finite(raw["tick_volume"])),
        }
        if bar["high"] < max(bar["open"], bar["close"], bar["low"]):
            raise ValueError("invalid high")
        if bar["low"] > min(bar["open"], bar["close"], bar["high"]):
            raise ValueError("invalid low")
        if min(bar["open"], bar["high"], bar["low"], bar["close"]) <= 0.0:
            raise ValueError("prices must be positive")
        result.append(bar)
    return result


def _atr(bars, period):
    if period < 1 or len(bars) < period + 1:
        return 0.0
    values = []
    for index in range(len(bars) - period, len(bars)):
        bar = bars[index]
        previous_close = bars[index - 1]["close"]
        values.append(max(
            bar["high"] - bar["low"],
            abs(bar["high"] - previous_close),
            abs(bar["low"] - previous_close),
        ))
    return sum(values) / len(values)


def _impact_profile(bars):
    if len(bars) < 8:
        return None
    signed_impacts = []
    travelled = 0.0
    for index in range(1, len(bars)):
        previous_close = bars[index - 1]["close"]
        close = bars[index]["close"]
        log_return = math.log(close / previous_close)
        signed_impacts.append(log_return / bars[index]["tick_volume"])
        travelled += abs(close - previous_close)
    absolute_total = sum(abs(value) for value in signed_impacts)
    if absolute_total <= 0.0 or travelled <= 0.0:
        return None
    signed_total = sum(signed_impacts)
    if signed_total == 0.0:
        return None
    side = 1 if signed_total > 0.0 else -1
    impact = statistics.mean(abs(value) for value in signed_impacts)
    directional = abs(signed_total) / absolute_total
    net_move = bars[-1]["close"] - bars[0]["close"]
    if net_move * side <= 0.0:
        return None
    path_efficiency = abs(net_move) / travelled
    volume = statistics.median(bar["tick_volume"] for bar in bars[1:])
    return impact, directional, side, net_move, path_efficiency, volume


def detect_s373(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S373 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        impact_ratio_min = float(c["IMPACT_RATIO_MIN"])
        directional_min = float(c["DIRECTIONAL_IMPACT_MIN"])
        volume_ratio_max = float(c["VOLUME_RATIO_MAX"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (impact_ratio_min, directional_min, volume_ratio_max)
    ):
        return _wait("Invalid config: impact gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 1)
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
        baseline_profiles = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _impact_profile(baseline[start:start + recent_count])
            if profile is not None:
                baseline_profiles.append(profile)
        recent_profile = _impact_profile(recent)
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
    if recent_profile is None or not baseline_profiles:
        return _wait("Liquidity-impact profile is unavailable")

    impact, directional, side, net_move, path_efficiency, recent_volume = (
        recent_profile
    )
    baseline_impact = statistics.median(
        profile[0] for profile in baseline_profiles
    )
    baseline_volume = statistics.median(
        profile[5] for profile in baseline_profiles
    )
    if baseline_impact <= 0.0 or baseline_volume <= 0.0:
        return _wait("Baseline liquidity profile is zero")
    impact_ratio = impact / baseline_impact
    volume_ratio = recent_volume / baseline_volume
    if impact_ratio < impact_ratio_min:
        return _wait(f"No price-impact expansion ({impact_ratio:.3f}x)")
    if directional < directional_min:
        return _wait(f"Price impact is not directional ({directional:.3f})")
    if volume_ratio > volume_ratio_max:
        return _wait(f"Participation expanded with price ({volume_ratio:.3f}x)")
    if path_efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Liquidity-vacuum path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Liquidity-vacuum net move is too small")

    body = float(event["close"]) - float(event["open"])
    candle_range = float(event["high"]) - float(event["low"])
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes price-impact direction")
    if abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if candle_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    close_fraction = (
        (float(event["close"]) - float(event["low"])) / candle_range
        if side > 0
        else (float(event["high"]) - float(event["close"])) / candle_range
    )
    if close_fraction < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Release lacks directional close control")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(float(event["close"]), 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor(
            (float(event["low"]) - sl_buffer + 1e-12) * 100.0
        ) / 100.0
    else:
        sl = math.ceil(
            (float(event["high"]) + sl_buffer - 1e-12) * 100.0
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
        "pattern": f"S373 {signal} Liquidity Impact {rr:g}R",
        "reason": (
            f"Amihud impact {impact_ratio:.4f}x, directional={directional:.4f}, "
            f"volume={volume_ratio:.4f}x, path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
