# -*- coding: utf-8 -*-
"""S358 - Variance-ratio trend-emergence release.

S358 applies a short-horizon variance-ratio test to closed returns.  A recent
multi-bar variance ratio above one and above disjoint baseline blocks indicates
positive serial dependence: displacement compounds across bars faster than a
random walk.  Direction, path efficiency, and a closed release must agree.

All variance-ratio and path inputs precede the release candle.  Entry is
next-open market, SL is beyond the closed release extreme plus ATR, and TP is
at least 7R.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 96,
    "RECENT_BARS": 24,
    "VR_HORIZON": 4,
    "VARIANCE_RATIO_MIN": 1.15,
    "VARIANCE_RATIO_JUMP_MIN": 0.15,
    "PATH_EFFICIENCY_MIN": 0.20,
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
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    "TP_RR": 12.0,
    "BE_RR": 0.05,
    "CANCEL_BARS": 3,
}


def _variance_ratio_profile(bars, horizon):
    if len(bars) < max(8, horizon + 4):
        return None
    closes = [float(bar["close"]) for bar in bars]
    if not all(math.isfinite(value) for value in closes):
        return None
    returns = [
        closes[index] - closes[index - 1]
        for index in range(1, len(closes))
    ]
    one_variance = statistics.pvariance(returns)
    if one_variance <= 1e-18:
        return None
    horizon_returns = [
        closes[index] - closes[index - horizon]
        for index in range(horizon, len(closes))
    ]
    if len(horizon_returns) < 3:
        return None
    ratio = statistics.pvariance(horizon_returns) / (
        horizon * one_variance
    )
    net_move = closes[-1] - closes[0]
    if abs(net_move) <= 1e-12:
        return None
    side = 1 if net_move > 0.0 else -1
    travelled = sum(abs(value) for value in returns)
    if travelled <= 0.0:
        return None
    efficiency = abs(net_move) / travelled
    return ratio, side, net_move, efficiency


def detect_s358(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after the multi-bar variance ratio expands."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        horizon = max(2, int(c["VR_HORIZON"]))
        ratio_min = float(c["VARIANCE_RATIO_MIN"])
        ratio_jump_min = float(c["VARIANCE_RATIO_JUMP_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if horizon >= recent_count:
        return _wait("Invalid config: VR horizon too long")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (ratio_min, ratio_jump_min)
    ):
        return _wait("Invalid config: variance-ratio gates are invalid")

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
        baseline_ratios = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _variance_ratio_profile(
                baseline[start:start + recent_count],
                horizon,
            )
            if profile is not None:
                baseline_ratios.append(profile[0])
        recent_profile = _variance_ratio_profile(recent, horizon)
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
    if recent_profile is None or not baseline_ratios:
        return _wait("Variance-ratio profile is unavailable")

    ratio, side, net_move, efficiency = recent_profile
    baseline_ratio = statistics.median(baseline_ratios)
    ratio_jump = ratio - baseline_ratio
    if ratio < ratio_min or ratio_jump < ratio_jump_min:
        return _wait(
            f"No variance-ratio expansion "
            f"({baseline_ratio:.3f}->{ratio:.3f}, "
            f"jump={ratio_jump:.3f})"
        )
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Variance-ratio path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Variance-ratio net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes variance-ratio direction")
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
        "pattern": f"S358 {signal} Variance Ratio {rr:g}R",
        "reason": (
            f"variance ratio q={horizon} "
            f"{baseline_ratio:.4f}->{ratio:.4f}, "
            f"jump={ratio_jump:.4f}, efficiency={efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
