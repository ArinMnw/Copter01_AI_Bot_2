# -*- coding: utf-8 -*-
"""S287 - Optimized Pettitt shift resumption, BUY-only 29.8R.

Pettitt's rank test detects a distribution-free location change in closed
prices. S287 waits for a one-bar counter-shift pullback and enters only when
the current closed candle resumes the direction of the detected regime shift.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "PETTITT_LOOKBACK": 64,
    "CHANGE_MIN_AGE": 8,
    "CHANGE_MAX_AGE": 24,
    "PETTITT_P_MAX": 0.025,
    "SHIFT_ATR_MIN": 1.25,
    "RESUME_BODY_ATR_MIN": 0.20,
    "RESUME_CLOSE_FRACTION": 0.55,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": False,
    "TP_RR": 29.80,
    "BE_RR": 0.70,
    "CANCEL_BARS": 3,
}


def _pettitt(values):
    """Return split index, statistic and approximate two-sided p-value."""
    size = len(values)
    if size < 8:
        return None, None, None
    counts = Counter(values)
    ranks = {}
    rank_start = 1
    for value in sorted(counts):
        rank_end = rank_start + counts[value] - 1
        ranks[value] = (rank_start + rank_end) / 2.0
        rank_start = rank_end + 1
    best_index = best_value = None
    best_abs = -1
    rank_sum = 0.0
    for split in range(1, size):
        rank_sum += ranks[values[split - 1]]
        statistic = 2.0 * rank_sum - split * (size + 1)
        magnitude = abs(statistic)
        if magnitude > best_abs:
            best_index, best_value, best_abs = split, statistic, magnitude
    denominator = size**3 + size**2
    p_value = min(1.0, 2.0 * math.exp(-6.0 * best_abs**2 / denominator))
    return best_index, best_value, p_value


def detect_s287(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a pullback resumption after a significant location shift."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        lookback = max(24, int(c["PETTITT_LOOKBACK"]))
        min_age = max(2, int(c["CHANGE_MIN_AGE"]))
        max_age = max(min_age, int(c["CHANGE_MAX_AGE"]))
        p_max = float(c["PETTITT_P_MAX"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(lookback + 3, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [bar["close"] for bar in bars[-lookback - 1:-1]]
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        AttributeError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    split, statistic, p_value = _pettitt(closes)
    if split is None:
        return _wait("Pettitt statistic is unavailable")
    change_age = lookback - split
    if not min_age <= change_age <= max_age:
        return _wait(f"Change point age is outside window ({change_age})")
    if p_value > p_max:
        return _wait(f"Location shift is not significant (p={p_value:.3f})")
    before = statistics.median(closes[:split])
    after = statistics.median(closes[split:])
    shift = after - before
    if abs(shift) < atr * float(c["SHIFT_ATR_MIN"]):
        return _wait(f"Location shift is too small ({shift / atr:.2f} ATR)")
    side = 1 if shift > 0.0 else -1
    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled by direction-survival filter")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled by direction-survival filter")

    pullback = bars[-2]
    event = bars[-1]
    pullback_body = pullback["close"] - pullback["open"]
    event_body = event["close"] - event["open"]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Resumption candle has zero range")
    if side * pullback_body >= 0.0:
        return _wait("Previous candle is not a counter-shift pullback")
    if side * event_body <= 0.0:
        return _wait("Current candle does not resume the location shift")
    if abs(event_body) < atr * float(c["RESUME_BODY_ATR_MIN"]):
        return _wait("Resumption body is too small versus ATR")
    close_location = (
        (event["close"] - event["low"]) / event_range
        if side > 0
        else (event["high"] - event["close"]) / event_range
    )
    if close_location < float(c["RESUME_CLOSE_FRACTION"]):
        return _wait("Resumption candle closes without directional control")

    entry = round(event["close"], 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        structural = min(pullback["low"], event["low"])
        sl = math.floor((structural - buffer + 1e-12) * 100.0) / 100.0
    else:
        structural = max(pullback["high"], event["high"])
        sl = math.ceil((structural + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Pullback risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Pullback risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    if side > 0:
        tp = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
    else:
        tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S287 {signal} Pettitt Shift Resume {rr:g}R",
        "reason": (
            f"Pettitt location shift resumes after one-bar pullback "
            f"(age={change_age}, p={p_value:.3f}, shift={shift / atr:.2f} ATR, "
            f"U={statistic})"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
