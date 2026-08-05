# -*- coding: utf-8 -*-
"""S371 - Realized-skewness tail-asymmetry release.

S371 estimates standardized realized skewness from closed log returns.  Recent
absolute skewness must expand versus disjoint baseline blocks, while its sign,
net displacement, path efficiency, and a fully closed release all agree.  The
setup follows a directional heavy tail rather than variance or volume alone.

All skewness and path features precede the release candle.  Entry is next-open
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
    "BASELINE_BARS": 60,
    "RECENT_BARS": 20,
    "SKEWNESS_MIN": 0.70,
    "SKEWNESS_RATIO_MIN": 1.20,
    "PATH_EFFICIENCY_MIN": 0.22,
    "NET_MOVE_ATR_MIN": 0.50,
    "RELEASE_BODY_ATR_MIN": 0.60,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.85,
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


def _skewness_profile(bars):
    if len(bars) < 8:
        return None
    closes = [float(bar["close"]) for bar in bars]
    if not all(math.isfinite(value) and value > 0.0 for value in closes):
        return None
    returns = [
        math.log(closes[index] / closes[index - 1])
        for index in range(1, len(closes))
    ]
    sum_squares = sum(value * value for value in returns)
    if sum_squares <= 1e-24:
        return None
    skewness = (
        math.sqrt(len(returns))
        * sum(value * value * value for value in returns)
        / (sum_squares ** 1.5)
    )
    net_move = closes[-1] - closes[0]
    travelled = sum(
        abs(closes[index] - closes[index - 1])
        for index in range(1, len(closes))
    )
    if (
        travelled <= 0.0
        or abs(net_move) <= 1e-12
        or abs(skewness) <= 1e-12
    ):
        return None
    side = 1 if skewness > 0.0 else -1
    if net_move * side <= 0.0:
        return None
    path_efficiency = abs(net_move) / travelled
    return abs(skewness), side, net_move, path_efficiency


def detect_s371(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after realized return skewness expands."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        skewness_min = float(c["SKEWNESS_MIN"])
        skewness_ratio_min = float(c["SKEWNESS_RATIO_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (skewness_min, skewness_ratio_min)
    ):
        return _wait("Invalid config: skewness gates are invalid")

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
        baseline_skewness = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _skewness_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_skewness.append(profile[0])
        recent_profile = _skewness_profile(recent)
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
    if recent_profile is None or not baseline_skewness:
        return _wait("Realized-skewness profile is unavailable")

    skewness, side, net_move, path_efficiency = recent_profile
    baseline_skew = statistics.median(baseline_skewness)
    if baseline_skew <= 0.0:
        return _wait("Baseline realized skewness is zero")
    skewness_ratio = skewness / baseline_skew
    if skewness < skewness_min or skewness_ratio < skewness_ratio_min:
        return _wait(
            f"No skewness expansion ({baseline_skew:.3f}->{skewness:.3f}, "
            f"ratio={skewness_ratio:.3f})"
        )
    if path_efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Skewed path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Skewed net move is too small")

    body = float(event["close"]) - float(event["open"])
    candle_range = float(event["high"]) - float(event["low"])
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes skewness direction")
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
        "pattern": f"S371 {signal} Realized Skewness {rr:g}R",
        "reason": (
            f"realized skew {baseline_skew:.4f}->{skewness:.4f}, "
            f"ratio={skewness_ratio:.4f}, path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
