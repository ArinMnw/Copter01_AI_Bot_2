# -*- coding: utf-8 -*-
"""S213 - NY-open impulse pullback continuation with a pullback-bar stop, 10R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 19,
    "SESSION_END_HOUR": 23,
    "IMPULSE_BARS": 6,
    "IMPULSE_MIN_ATR": 2.00,
    "RETRACE_MIN_FRACTION": 0.20,
    "RETRACE_MAX_FRACTION": 0.60,
    "ENTRY_RETRACE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 6,
}


def detect_s213(rates, tf, dt_bkk, cfg):
    """Join the New-York opening impulse on its first orderly pullback."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        impulse_bars = max(3, int(c["IMPULSE_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = impulse_bars + period + 6
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside New-York opening window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    pullback = bars[-1]
    impulse = bars[-impulse_bars - 1:-1]
    impulse_move = impulse[-1]["close"] - impulse[0]["open"]
    if abs(impulse_move) < atr * float(c["IMPULSE_MIN_ATR"]):
        return _wait("No opening impulse of sufficient size")
    side = 1 if impulse_move > 0.0 else -1
    impulse_start = impulse[0]["open"]
    impulse_end = impulse[-1]["close"]

    body = pullback["close"] - pullback["open"]
    if side * body >= 0.0:
        return _wait("No counter-directional pullback bar yet")
    retrace = side * (impulse_end - pullback["close"]) / abs(impulse_move)
    if not (float(c["RETRACE_MIN_FRACTION"]) <= retrace
            <= float(c["RETRACE_MAX_FRACTION"])):
        return _wait(f"Pullback retrace outside band ({retrace:.2f})")

    entry_level = impulse_end - side * abs(impulse_move) * float(
        c["ENTRY_RETRACE_FRACTION"]
    )
    entry = round(entry_level, 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        if entry >= pullback["close"]:
            return _wait("BUY limit is not below the pullback close")
        sl = math.floor((pullback["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        if entry <= pullback["close"]:
            return _wait("SELL limit is not above the pullback close")
        sl = math.ceil((pullback["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Pullback risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Pullback risk too large versus price")

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
        "order_type": "limit",
        "pattern": f"S213 {signal} NY Impulse Pullback {rr:g}R",
        "reason": (f"NY impulse {impulse_move / atr:+.1f} ATR, pullback "
                   f"{retrace:.0%}; continuation limit"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
