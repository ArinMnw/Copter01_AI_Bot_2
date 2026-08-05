# -*- coding: utf-8 -*-
"""S336 - Range-volume liquidity-elasticity release.

S336 fits log(relative intrabar range) on log(tick volume) in disjoint
baseline and recent samples.  A rising positive elasticity with improving
explanatory power means increments in activity are producing disproportionately
larger price ranges, consistent with thinning liquidity and rising price impact.

Every regression input precedes the release candle.  Entry is next-open market,
SL is beyond the closed release extreme plus ATR, and TP is at least 7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 64,
    "RECENT_BARS": 24,
    "RECENT_ELASTICITY_MIN": 0.25,
    "ELASTICITY_JUMP_MIN": 0.18,
    "RECENT_R2_MIN": 0.10,
    "R2_JUMP_MIN": 0.03,
    "RECENT_VOLUME_RATIO_MIN": 1.00,
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
    "TP_RR": 8.0,
    "BE_RR": 0.08,
    "CANCEL_BARS": 3,
}


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _range_volume_elasticity(bars):
    x_values = []
    y_values = []
    for bar in bars:
        close = float(bar["close"])
        candle_range = float(bar["high"]) - float(bar["low"])
        volume = float(bar["tick_volume"])
        if (
            not all(math.isfinite(value) for value in (close, candle_range, volume))
            or close <= 0.0
            or candle_range <= 0.0
            or volume <= 0.0
        ):
            return None
        x_values.append(math.log(volume))
        y_values.append(math.log(candle_range / close))
    if len(x_values) < 8:
        return None
    x_mean = _mean(x_values)
    y_mean = _mean(y_values)
    x_variance = sum((value - x_mean) ** 2 for value in x_values)
    y_variance = sum((value - y_mean) ** 2 for value in y_values)
    if x_variance <= 0.0 or y_variance <= 0.0:
        return None
    covariance = sum(
        (x_value - x_mean) * (y_value - y_mean)
        for x_value, y_value in zip(x_values, y_values)
    )
    slope = covariance / x_variance
    r_squared = covariance * covariance / (x_variance * y_variance)
    return slope, max(0.0, min(1.0, r_squared)), _mean([
        float(bar["tick_volume"]) for bar in bars
    ])


def detect_s336(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after range-volume elasticity expands."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        elasticity_min = float(c["RECENT_ELASTICITY_MIN"])
        elasticity_jump_min = float(c["ELASTICITY_JUMP_MIN"])
        recent_r2_min = float(c["RECENT_R2_MIN"])
        r2_jump_min = float(c["R2_JUMP_MIN"])
        volume_ratio_min = float(c["RECENT_VOLUME_RATIO_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if (
        not all(
            math.isfinite(value) and value >= 0.0
            for value in (
                elasticity_min,
                elasticity_jump_min,
                recent_r2_min,
                r2_jump_min,
                volume_ratio_min,
            )
        )
        or recent_r2_min > 1.0
        or r2_jump_min > 1.0
    ):
        return _wait("Invalid config: elasticity gates are invalid")

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
        baseline_profile = _range_volume_elasticity(baseline)
        recent_profile = _range_volume_elasticity(recent)
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
        return _wait("Range-volume elasticity is unavailable")

    baseline_slope, baseline_r2, baseline_volume = baseline_profile
    recent_slope, recent_r2, recent_volume = recent_profile
    slope_jump = recent_slope - baseline_slope
    r2_jump = recent_r2 - baseline_r2
    volume_ratio = recent_volume / baseline_volume if baseline_volume > 0.0 else 0.0
    if (
        recent_slope < elasticity_min
        or slope_jump < elasticity_jump_min
        or recent_r2 < recent_r2_min
        or r2_jump < r2_jump_min
        or volume_ratio < volume_ratio_min
    ):
        return _wait(
            f"No liquidity-elasticity expansion "
            f"(slope={baseline_slope:.3f}->{recent_slope:.3f}, "
            f"r2={baseline_r2:.3f}->{recent_r2:.3f}, "
            f"volume={volume_ratio:.3f}x)"
        )

    net_move = recent[-1]["close"] - recent[0]["close"]
    travelled = sum(
        abs(recent[index]["close"] - recent[index - 1]["close"])
        for index in range(1, len(recent))
    )
    if travelled <= 0.0:
        return _wait("Recent path has no movement")
    side = 1 if net_move > 0.0 else -1
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes elasticity-path direction")
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
        "pattern": f"S336 {signal} Liquidity Elasticity {rr:g}R",
        "reason": (
            f"elasticity {baseline_slope:.4f}->{recent_slope:.4f}, "
            f"jump={slope_jump:.4f}, r2={recent_r2:.4f}, "
            f"volume={volume_ratio:.4f}x"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
