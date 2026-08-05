# -*- coding: utf-8 -*-
"""S334 - Directional realized-semivariance rotation release.

S334 partitions squared closed returns into positive and negative realized
semivariance.  A recent rotation toward one side, relative to a disjoint
baseline, measures where directional volatility is being spent.  A cap on the
largest squared-return contribution rejects single-jump artifacts.

Every estimator input precedes the release candle.  Entry is next-open market,
the stop is beyond the release extreme plus ATR, and TP is at least 7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 64,
    "RECENT_RETURNS": 20,
    "RECENT_SEMIVARIANCE_SHARE_MIN": 0.68,
    "SEMIVARIANCE_SHARE_JUMP_MIN": 0.12,
    "SEMIVARIANCE_ASYMMETRY_MIN": 0.36,
    "MAX_SINGLE_RETURN_ENERGY_SHARE": 0.55,
    "PATH_EFFICIENCY_MIN": 0.22,
    "NET_MOVE_ATR_MIN": 0.55,
    "RELEASE_BODY_ATR_MIN": 0.72,
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
    "TP_RR": 8.5,
    "BE_RR": 0.06,
    "CANCEL_BARS": 3,
}


def _semivariance_profile(bars):
    positive = 0.0
    negative = 0.0
    largest = 0.0
    for index in range(1, len(bars)):
        previous = float(bars[index - 1]["close"])
        current = float(bars[index]["close"])
        if (
            not math.isfinite(previous)
            or not math.isfinite(current)
            or previous <= 0.0
            or current <= 0.0
        ):
            return None
        value = math.log(current / previous)
        energy = value * value
        largest = max(largest, energy)
        if value > 0.0:
            positive += energy
        elif value < 0.0:
            negative += energy
    total = positive + negative
    if total <= 0.0:
        return None
    return positive / total, negative / total, largest / total


def detect_s334(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after realized semivariance rotates to one side."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_RETURNS"]))
        recent_count = max(8, int(c["RECENT_RETURNS"]))
        recent_min = float(c["RECENT_SEMIVARIANCE_SHARE_MIN"])
        jump_min = float(c["SEMIVARIANCE_SHARE_JUMP_MIN"])
        asymmetry_min = float(c["SEMIVARIANCE_ASYMMETRY_MIN"])
        maximum_single_share = float(c["MAX_SINGLE_RETURN_ENERGY_SHARE"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if (
        not all(
            math.isfinite(value) and 0.0 <= value <= 1.0
            for value in (
                recent_min, jump_min, asymmetry_min, maximum_single_share
            )
        )
        or maximum_single_share <= 0.0
    ):
        return _wait("Invalid config: semivariance gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 3)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 2:-1]
        baseline = history[:baseline_count + 1]
        recent = history[baseline_count:]
        baseline_profile = _semivariance_profile(baseline)
        recent_profile = _semivariance_profile(recent)
        atr = _atr(bars[:-1], period)
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        ZeroDivisionError,
        AttributeError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    if baseline_profile is None or recent_profile is None:
        return _wait("Realized semivariance is unavailable")

    baseline_positive, baseline_negative, _ = baseline_profile
    recent_positive, recent_negative, recent_largest = recent_profile
    side = 1 if recent_positive > recent_negative else -1
    recent_side = recent_positive if side > 0 else recent_negative
    recent_other = recent_negative if side > 0 else recent_positive
    baseline_side = baseline_positive if side > 0 else baseline_negative
    share_jump = recent_side - baseline_side
    asymmetry = recent_side - recent_other
    if (
        recent_side < recent_min
        or share_jump < jump_min
        or asymmetry < asymmetry_min
    ):
        return _wait(
            f"No semivariance rotation ({recent_side:.3f}, "
            f"jump={share_jump:.3f}, asym={asymmetry:.3f})"
        )
    if recent_largest > maximum_single_share:
        return _wait(
            f"Semivariance is single-jump dominated ({recent_largest:.3f})"
        )

    net_move = recent[-1]["close"] - recent[0]["close"]
    travelled = sum(
        abs(recent[index]["close"] - recent[index - 1]["close"])
        for index in range(1, len(recent))
    )
    if travelled <= 0.0:
        return _wait("Recent path has no movement")
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move is too small")
    if net_move * side <= 0.0:
        return _wait("Recent path opposes semivariance direction")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes semivariance direction")
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
        "pattern": f"S334 {signal} Semivariance Rotation {rr:g}R",
        "reason": (
            f"semivariance {baseline_side:.4f}->{recent_side:.4f}, "
            f"jump={share_jump:.4f}, asymmetry={asymmetry:.4f}, "
            f"largest={recent_largest:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
