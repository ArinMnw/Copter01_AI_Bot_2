# -*- coding: utf-8 -*-
"""S252 - ATR directional-change regime reversal, 10R.

Directional-change analysis samples price by events rather than fixed time.
The latest up/down regime and its extreme are reconstructed from closed bars
using an ATR-scaled threshold.  A fresh reversal event on the current closed
bar is traded with the event extreme as the structural stop.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "DC_LOOKBACK": 96,
    "DC_THRESHOLD_ATR": 0.75,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "MIN_EVENT_BODY_ATR": 0.25,
    "MIN_EVENT_BODY_FRACTION": 0.55,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _directional_change_state(closes, threshold):
    high = low = float(closes[0])
    mode = 0
    for close in closes[1:]:
        close = float(close)
        if mode == 0:
            high = max(high, close)
            low = min(low, close)
            if close - low >= threshold:
                mode, high = 1, close
            elif high - close >= threshold:
                mode, low = -1, close
        elif mode > 0:
            high = max(high, close)
            if high - close >= threshold:
                mode, low = -1, close
        else:
            low = min(low, close)
            if close - low >= threshold:
                mode, high = 1, close
    return mode, high, low


def detect_s252(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a fresh ATR-scaled directional-change reversal event."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        lookback = max(24, int(c["DC_LOOKBACK"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(period + 5, lookback + 3)
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
    threshold = atr * float(c["DC_THRESHOLD_ATR"])
    if threshold <= 0.0:
        return _wait("Directional-change threshold is zero")

    closes = [bar["close"] for bar in bars[-lookback - 1:-1]]
    mode, high, low = _directional_change_state(closes, threshold)
    event = bars[-1]
    close = event["close"]
    body = close - event["open"]
    event_range = event["high"] - event["low"]
    if mode > 0 and high - close >= threshold and body < 0.0:
        side = -1
        structural_extreme = max(high, event["high"])
    elif mode < 0 and close - low >= threshold and body > 0.0:
        side = 1
        structural_extreme = min(low, event["low"])
    else:
        return _wait("No fresh directional-change reversal")
    if side > 0 and not bool(c["ALLOW_BUY"]):
        return _wait("BUY directional-change branch is disabled")
    if side < 0 and not bool(c["ALLOW_SELL"]):
        return _wait("SELL directional-change branch is disabled")
    if event_range <= 0.0:
        return _wait("Event bar range is zero")
    if abs(body) < atr * float(c["MIN_EVENT_BODY_ATR"]):
        return _wait("Directional-change body is too small")
    if abs(body) < event_range * float(c["MIN_EVENT_BODY_FRACTION"]):
        return _wait("Directional-change close lacks efficiency")

    entry = round(close, 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor((structural_extreme - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((structural_extreme + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Directional-change risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Directional-change risk too large versus price")

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
        "pattern": f"S252 {signal} ATR Directional-Change Reversal {rr:g}R",
        "reason": (
            f"Fresh {signal} directional-change event "
            f"(threshold={float(c['DC_THRESHOLD_ATR']):.2f} ATR)"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
