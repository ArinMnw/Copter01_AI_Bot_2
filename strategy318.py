# -*- coding: utf-8 -*-
"""S318 - Corwin-Schultz implied-spread compression release.

The Corwin-Schultz two-period high/low estimator separates an implied
effective-spread component from range volatility.  S318 looks for a robust
drop in this microstructure cost between non-overlapping baseline and recent
samples, then follows an efficient structural release while liquidity is
estimated to be improving.

Only closed bars before the release enter the estimator.  Entry is next-open
market, the stop is beyond the release extreme plus ATR, and TP is at least 7R.
"""

from __future__ import annotations

import math
from statistics import median

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_ESTIMATES": 48,
    "RECENT_ESTIMATES": 16,
    "SPREAD_RATIO_MAX": 0.78,
    "BASELINE_SPREAD_MIN": 0.00010,
    "PATH_EFFICIENCY_MIN": 0.30,
    "NET_MOVE_ATR_MIN": 0.60,
    "BREAKOUT_LOOKBACK": 10,
    "BREAKOUT_BUFFER_ATR": 0.01,
    "RELEASE_BODY_ATR_MIN": 0.60,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.80,
    "SESSION_START_HOUR": 7,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 8.0,
    "BE_RR": 0.10,
    "CANCEL_BARS": 3,
}


def _corwin_schultz(first, second):
    """Return the non-negative two-bar Corwin-Schultz spread estimate."""
    values = (
        first["high"], first["low"], second["high"], second["low"]
    )
    if any(not math.isfinite(value) or value <= 0.0 for value in values):
        return None
    beta = (
        math.log(first["high"] / first["low"]) ** 2
        + math.log(second["high"] / second["low"]) ** 2
    )
    two_bar_high = max(first["high"], second["high"])
    two_bar_low = min(first["low"], second["low"])
    gamma = math.log(two_bar_high / two_bar_low) ** 2
    denominator = 3.0 - 2.0 * math.sqrt(2.0)
    alpha = (
        (math.sqrt(2.0 * beta) - math.sqrt(beta)) / denominator
        - math.sqrt(gamma / denominator)
    )
    alpha = max(0.0, alpha)
    exponential = math.exp(min(alpha, 50.0))
    return 2.0 * (exponential - 1.0) / (1.0 + exponential)


def detect_s318(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a structural release after implied-spread compression."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(8, int(c["BASELINE_ESTIMATES"]))
        recent_count = max(6, int(c["RECENT_ESTIMATES"]))
        breakout_lookback = max(3, int(c["BREAKOUT_LOOKBACK"]))
        ratio_max = float(c["SPREAD_RATIO_MAX"])
        baseline_min = float(c["BASELINE_SPREAD_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (ratio_max, baseline_min)
    ):
        return _wait("Invalid config: spread thresholds must be finite")

    total_estimates = baseline_count + recent_count
    required = max(total_estimates + 4, period + breakout_lookback + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside liquid session")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-total_estimates - 2:-1]
        estimates = [
            _corwin_schultz(history[index - 1], history[index])
            for index in range(1, len(history))
        ]
        if any(value is None for value in estimates):
            return _wait("Corwin-Schultz estimate is unavailable")
        baseline = estimates[:baseline_count]
        recent = estimates[baseline_count:]
        baseline_spread = median(baseline)
        recent_spread = median(recent)
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
    if baseline_spread < baseline_min:
        return _wait(f"Baseline implied spread is too small ({baseline_spread:.6f})")
    spread_ratio = recent_spread / baseline_spread
    if spread_ratio > ratio_max:
        return _wait(f"Implied spread has not compressed ({spread_ratio:.3f})")

    recent_bars = history[-recent_count - 1:]
    net_move = recent_bars[-1]["close"] - recent_bars[0]["close"]
    travelled = sum(
        abs(recent_bars[index]["close"] - recent_bars[index - 1]["close"])
        for index in range(1, len(recent_bars))
    )
    if travelled <= 0.0:
        return _wait("Recent path has no movement")
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move is too small")
    side = 1 if net_move > 0.0 else -1

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes the compressed-liquidity path")
    if abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if candle_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    structure = bars[-breakout_lookback - 1:-1]
    buffer = atr * float(c["BREAKOUT_BUFFER_ATR"])
    if side > 0:
        structure_level = max(bar["high"] for bar in structure)
        close_fraction = (event["close"] - event["low"]) / candle_range
        if event["close"] <= structure_level + buffer:
            return _wait("BUY release does not break structure")
    else:
        structure_level = min(bar["low"] for bar in structure)
        close_fraction = (event["high"] - event["close"]) / candle_range
        if event["close"] >= structure_level - buffer:
            return _wait("SELL release does not break structure")
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
        sl = math.floor((event["low"] - sl_buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + sl_buffer - 1e-12) * 100.0) / 100.0
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
        "pattern": f"S318 {signal} CS Spread Compression {rr:g}R",
        "reason": (
            f"Corwin-Schultz spread {baseline_spread:.6f}->"
            f"{recent_spread:.6f}, ratio={spread_ratio:.3f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
