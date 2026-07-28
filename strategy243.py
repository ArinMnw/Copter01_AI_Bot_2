# -*- coding: utf-8 -*-
"""S243 - Positive CLV-pressure pullback engulf continuation, 10R.

Persistent positive volume-weighted CLV defines the long-side auction regime.
A bearish pullback followed by a bullish close above the pullback high provides
a concrete continuation trigger and a two-bar structural stop.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "PRESSURE_WINDOW": 24,
    "MIN_CLV_PRESSURE": 0.18,
    "MIN_PULLBACK_BODY_ATR": 0.15,
    "MIN_TRIGGER_BODY_ATR": 0.25,
    "MIN_TRIGGER_BODY_FRACTION": 0.55,
    "MAX_TWO_BAR_RANGE_ATR": 2.25,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s243(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Buy a bullish pullback engulf inside positive CLV pressure."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        pressure_window = max(8, int(c["PRESSURE_WINDOW"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(period + 5, pressure_window + 4)
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

    history = bars[-pressure_window - 2:-2]
    weighted_clv = total_volume = 0.0
    for bar in history:
        bar_range = bar["high"] - bar["low"]
        volume = max(0.0, float(bar["tick_volume"]))
        if bar_range > 0.0 and volume > 0.0:
            clv = (
                (bar["close"] - bar["low"])
                - (bar["high"] - bar["close"])
            ) / bar_range
            weighted_clv += volume * clv
            total_volume += volume
    if total_volume <= 0.0:
        return _wait("Tick volume is unavailable")
    pressure = weighted_clv / total_volume
    if pressure < float(c["MIN_CLV_PRESSURE"]):
        return _wait(f"Positive CLV pressure is insufficient ({pressure:.2f})")

    pullback, trigger = bars[-2], bars[-1]
    pullback_body = pullback["open"] - pullback["close"]
    trigger_body = trigger["close"] - trigger["open"]
    trigger_range = trigger["high"] - trigger["low"]
    if pullback_body < atr * float(c["MIN_PULLBACK_BODY_ATR"]):
        return _wait("No meaningful bearish pullback")
    if trigger_body < atr * float(c["MIN_TRIGGER_BODY_ATR"]):
        return _wait("Bullish trigger body is too small")
    if trigger["close"] <= pullback["high"]:
        return _wait("Bullish trigger did not engulf the pullback high")
    if trigger_range <= 0.0:
        return _wait("Trigger bar range is zero")
    if trigger_body < trigger_range * float(c["MIN_TRIGGER_BODY_FRACTION"]):
        return _wait("Bullish trigger lacks close efficiency")
    two_bar_low = min(pullback["low"], trigger["low"])
    two_bar_high = max(pullback["high"], trigger["high"])
    if two_bar_high - two_bar_low > atr * float(c["MAX_TWO_BAR_RANGE_ATR"]):
        return _wait("Pullback-trigger structure is too wide")

    entry = round(trigger["close"], 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    sl = math.floor((two_bar_low - buffer + 1e-12) * 100.0) / 100.0
    risk = entry - sl
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Pullback risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Pullback risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    tp = math.ceil((entry + rr * risk - 1e-12) * 100.0) / 100.0
    return {
        "signal": "BUY",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S243 BUY Positive-CLV Pullback Engulf {rr:g}R",
        "reason": (
            f"Bullish pullback engulf inside positive CLV pressure "
            f"(pressure={pressure:.2f})"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
