# -*- coding: utf-8 -*-
"""S249 - Hurst anti-persistent failed-sweep fade, 10R.

When multi-scale Hurst is low, returns are expected to alternate rather than
persist.  S249 fades a fresh range sweep that closes back inside, using the
sweep wick as a short structural stop.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy248 import _hurst_rs


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "HURST_WINDOW": 64,
    "HURST_SCALES": (8, 16, 32),
    "HURST_MAX": 0.40,
    "SWEEP_RANGE_BARS": 12,
    "MIN_SWEEP_ATR": 0.03,
    "MIN_RECLAIM_FRACTION": 0.15,
    "MIN_BODY_ATR": 0.15,
    "MIN_WICK_FRACTION": 0.35,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s249(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a failed range sweep in an anti-persistent return regime."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(32, int(c["HURST_WINDOW"]))
        scales = tuple(sorted({max(4, int(value)) for value in c["HURST_SCALES"]}))
        range_bars = max(4, int(c["SWEEP_RANGE_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(period + 5, window + 3, range_bars + 3)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [bar["close"] for bar in bars[-window - 2:-1]]
        if min(closes) <= 0.0:
            return _wait("Non-positive close")
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
        hurst = _hurst_rs(returns, scales)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0 or hurst is None:
        return _wait("ATR or Hurst estimate is unavailable")
    if hurst > float(c["HURST_MAX"]):
        return _wait(f"Return path is not anti-persistent (H={hurst:.2f})")

    structure = bars[-range_bars - 1:-1]
    range_high = max(bar["high"] for bar in structure)
    range_low = min(bar["low"] for bar in structure)
    reclaim = bars[-1]
    body = reclaim["close"] - reclaim["open"]
    bar_range = reclaim["high"] - reclaim["low"]
    if bar_range <= 0.0:
        return _wait("Reclaim bar range is zero")
    if (
        reclaim["high"] >= range_high + atr * float(c["MIN_SWEEP_ATR"])
        and reclaim["close"] < range_high
        and body < -atr * float(c["MIN_BODY_ATR"])
    ):
        side = -1
        reclaim_fraction = (range_high - reclaim["close"]) / bar_range
        wick = reclaim["high"] - max(reclaim["open"], reclaim["close"])
    elif (
        reclaim["low"] <= range_low - atr * float(c["MIN_SWEEP_ATR"])
        and reclaim["close"] > range_low
        and body > atr * float(c["MIN_BODY_ATR"])
    ):
        side = 1
        reclaim_fraction = (reclaim["close"] - range_low) / bar_range
        wick = min(reclaim["open"], reclaim["close"]) - reclaim["low"]
    else:
        return _wait("No directional failed range sweep")
    if reclaim_fraction < float(c["MIN_RECLAIM_FRACTION"]):
        return _wait("Sweep reclaim is too shallow")
    if wick < bar_range * float(c["MIN_WICK_FRACTION"]):
        return _wait("Sweep bar lacks rejection wick")

    entry = round(reclaim["close"], 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor((reclaim["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((reclaim["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Sweep risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Sweep risk too large versus price")

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
        "pattern": f"S249 {signal} Hurst Anti-Persistent Sweep Fade {rr:g}R",
        "reason": f"Failed range sweep in anti-persistent regime (H={hurst:.2f})",
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
