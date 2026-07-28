# -*- coding: utf-8 -*-
"""S234 - US-window Parkinson volatility-compression breakout, 10R.

This is the estimator ablation for S233.  The scheduled 17:00-19:00 BKK window,
range-break geometry, and risk model stay fixed; only the compression estimator
changes from Rogers-Satchell OHLC variance to Parkinson high-low variance.  A
pass would support a broader scheduled compression edge rather than an
RS-specific historical fit.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 19,
    "RANGE_BARS": 12,
    "PARKINSON_SHORT_WINDOW": 12,
    "PARKINSON_LONG_WINDOW": 72,
    "PARKINSON_COMPRESSION_MAX": 0.65,
    "BREAK_BODY_MIN_FRACTION": 0.55,
    "BREAK_BODY_MIN_ATR": 0.30,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _parkinson_variance(bar):
    high = float(bar["high"])
    low = float(bar["low"])
    if low <= 0.0 or high < low:
        return 0.0
    log_range = math.log(high / low)
    return log_range * log_range / (4.0 * math.log(2.0))


def detect_s234(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade an efficient US-window range break after Parkinson compression."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        range_bars = max(4, int(c["RANGE_BARS"]))
        short_window = max(4, int(c["PARKINSON_SHORT_WINDOW"]))
        long_window = max(
            short_window + 4, int(c["PARKINSON_LONG_WINDOW"])
        )
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(period + range_bars + 5, long_window + 3)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    history = bars[-long_window - 1:-1]
    variance = [_parkinson_variance(bar) for bar in history]
    long_variance = sum(variance) / len(variance)
    short_variance = sum(variance[-short_window:]) / short_window
    if long_variance <= 0.0:
        return _wait("Long Parkinson variance is zero")
    compression_ratio = short_variance / long_variance
    if compression_ratio > float(c["PARKINSON_COMPRESSION_MAX"]):
        return _wait(
            f"Parkinson volatility is not compressed "
            f"(ratio={compression_ratio:.2f})"
        )

    compressed = bars[-range_bars - 1:-1]
    range_high = max(bar["high"] for bar in compressed)
    range_low = min(bar["low"] for bar in compressed)
    if range_high <= range_low:
        return _wait("Compressed range is degenerate")
    breakout = bars[-1]
    body = breakout["close"] - breakout["open"]
    bar_range = breakout["high"] - breakout["low"]
    if breakout["close"] > range_high and body > 0.0:
        side = 1
    elif breakout["close"] < range_low and body < 0.0:
        side = -1
    else:
        return _wait("No directional break of the compressed range")
    if bar_range <= 0.0:
        return _wait("Breakout bar range is zero")
    if abs(body) < bar_range * float(c["BREAK_BODY_MIN_FRACTION"]):
        return _wait("Breakout bar lacks directional efficiency")
    if abs(body) < atr * float(c["BREAK_BODY_MIN_ATR"]):
        return _wait("Breakout body is too small versus ATR")

    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(breakout["close"], 2)
    if side > 0:
        sl = math.floor((breakout["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((breakout["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Parkinson-break risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Parkinson-break risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    if side > 0:
        signal = "BUY"
        tp = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
    else:
        signal = "SELL"
        tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S234 {signal} US Parkinson Compression Break {rr:g}R",
        "reason": (
            f"US-window efficient break after Parkinson compression "
            f"(short/long={compression_ratio:.2f})"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
