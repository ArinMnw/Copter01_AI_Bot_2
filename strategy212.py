# -*- coding: utf-8 -*-
"""S212 - Quiet-compression ignition drive with a breakout-bar stop, 10R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "RANGE_BARS": 12,
    "QUIET_LOOKBACK": 288,
    "QUIET_QUANTILE": 0.15,
    "BREAK_BODY_MIN_FRACTION": 0.40,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s212(rates, tf, dt_bkk, cfg):
    """Trade the ignition drive out of an unusually quiet micro-range."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        range_bars = max(4, int(c["RANGE_BARS"]))
        quiet_lookback = max(48, int(c["QUIET_LOOKBACK"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = quiet_lookback + range_bars + period + 4
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    micro_range = bars[-range_bars - 1:-1]
    range_high = max(bar["high"] for bar in micro_range)
    range_low = min(bar["low"] for bar in micro_range)
    range_size = range_high - range_low
    if range_size <= 0.0:
        return _wait("Micro range is degenerate")
    history = bars[-quiet_lookback - range_bars - 1:-1]
    rolling = []
    for index in range(range_bars, len(history) + 1):
        window = history[index - range_bars:index]
        rolling.append(max(b["high"] for b in window) - min(b["low"] for b in window))
    quiet_ceiling = _quantile(rolling, c["QUIET_QUANTILE"])
    if range_size > quiet_ceiling:
        return _wait("Micro range is not unusually quiet")

    breakout = bars[-1]
    body = breakout["close"] - breakout["open"]
    if breakout["close"] > range_high and body > 0.0:
        side = 1
    elif breakout["close"] < range_low and body < 0.0:
        side = -1
    else:
        return _wait("No ignition drive out of the quiet range")
    if abs(body) < range_size * float(c["BREAK_BODY_MIN_FRACTION"]):
        return _wait("Ignition body is too small versus the quiet range")

    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(breakout["close"], 2)
    if side > 0:
        sl = math.floor((breakout["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((breakout["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Ignition risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Ignition risk too large versus price")

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
        "pattern": f"S212 {signal} Quiet Ignition {rr:g}R",
        "reason": (f"Ignition out of quiet {range_size:.2f} range "
                   f"(<= q{float(c['QUIET_QUANTILE']):g} of rolling ranges)"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
