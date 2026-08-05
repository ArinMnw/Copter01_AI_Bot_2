# -*- coding: utf-8 -*-
"""S364 - Roll implied-spread compression release.

S364 estimates the Roll microstructure spread from negative lag-one covariance
of closed returns.  A recent contraction versus disjoint baseline blocks
indicates reduced bid-ask bounce and cleaner price discovery.  Directional
path efficiency and a closed release must confirm continuation.

All covariance and path inputs precede the release candle.  Entry is next-open
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
    "ROLL_SPREAD_RATIO_MAX": 0.78,
    "PATH_EFFICIENCY_MIN": 0.20,
    "NET_MOVE_ATR_MIN": 0.50,
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


def _roll_profile(bars):
    if len(bars) < 8:
        return None
    closes = [float(bar["close"]) for bar in bars]
    if not all(math.isfinite(value) for value in closes):
        return None
    returns = [
        closes[index] - closes[index - 1]
        for index in range(1, len(closes))
    ]
    if len(returns) < 5:
        return None
    previous = returns[:-1]
    current = returns[1:]
    previous_mean = sum(previous) / len(previous)
    current_mean = sum(current) / len(current)
    covariance = sum(
        (left - previous_mean) * (right - current_mean)
        for left, right in zip(previous, current)
    ) / len(previous)
    if covariance >= -1e-18:
        return None
    implied_spread = 2.0 * math.sqrt(-covariance)
    net_move = closes[-1] - closes[0]
    if implied_spread <= 0.0 or abs(net_move) <= 1e-12:
        return None
    side = 1 if net_move > 0.0 else -1
    travelled = sum(abs(value) for value in returns)
    if travelled <= 0.0:
        return None
    path_efficiency = abs(net_move) / travelled
    return implied_spread, side, net_move, path_efficiency


def detect_s364(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow directional release after the Roll spread proxy contracts."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        spread_ratio_max = float(c["ROLL_SPREAD_RATIO_MAX"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if (
        not math.isfinite(spread_ratio_max)
        or not 0.0 < spread_ratio_max <= 1.0
    ):
        return _wait("Invalid config: Roll spread ratio is invalid")

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
        baseline_spreads = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _roll_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_spreads.append(profile[0])
        recent_profile = _roll_profile(recent)
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
    if recent_profile is None or not baseline_spreads:
        return _wait("Roll spread profile is unavailable")

    implied_spread, side, net_move, path_efficiency = recent_profile
    baseline_spread = statistics.median(baseline_spreads)
    if baseline_spread <= 0.0:
        return _wait("Baseline Roll spread is zero")
    spread_ratio = implied_spread / baseline_spread
    if spread_ratio > spread_ratio_max:
        return _wait(f"No Roll spread compression ({spread_ratio:.3f}x)")
    if path_efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Compressed-spread path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Compressed-spread net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes compressed-spread path")
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
        "pattern": f"S364 {signal} Roll Compression {rr:g}R",
        "reason": (
            f"Roll spread {baseline_spread:.4f}->{implied_spread:.4f}, "
            f"ratio={spread_ratio:.4f}, path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
