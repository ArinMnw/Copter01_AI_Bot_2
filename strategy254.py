# -*- coding: utf-8 -*-
"""S254 - VPIN-style informed-flow toxicity breakout, 10R.

Each bar's tick volume is probabilistically allocated to buy/sell flow from its
standardized open-close move.  High absolute volume imbalance (VPIN proxy) plus
coherent signed flow must align with an efficient structural range break.
"""

from __future__ import annotations

import math
from statistics import pstdev

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "FLOW_WINDOW": 48,
    "BREAK_RANGE_BARS": 8,
    "VPIN_MIN": 0.35,
    "SIGNED_FLOW_MIN": 0.12,
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


def detect_s254(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade an efficient break aligned with toxic signed volume flow."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        flow_window = max(16, int(c["FLOW_WINDOW"]))
        range_bars = max(4, int(c["BREAK_RANGE_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(period + 5, flow_window + 3, range_bars + 3)
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

    history = bars[-flow_window - 1:-1]
    price_changes = [
        history[index]["close"] - history[index - 1]["close"]
        for index in range(1, len(history))
    ]
    sigma = pstdev(price_changes)
    if sigma <= 0.0:
        return _wait("Flow-allocation volatility is zero")
    signed_volume = absolute_imbalance = total_volume = 0.0
    root_two = math.sqrt(2.0)
    for bar in history:
        volume = max(0.0, float(bar["tick_volume"]))
        if volume <= 0.0:
            continue
        zscore = (bar["close"] - bar["open"]) / sigma
        signed_fraction = math.erf(zscore / root_two)
        imbalance = volume * signed_fraction
        signed_volume += imbalance
        absolute_imbalance += abs(imbalance)
        total_volume += volume
    if total_volume <= 0.0:
        return _wait("Tick volume is unavailable")
    vpin = absolute_imbalance / total_volume
    signed_flow = signed_volume / total_volume
    if vpin < float(c["VPIN_MIN"]):
        return _wait(f"Flow toxicity is low (VPIN={vpin:.2f})")
    if abs(signed_flow) < float(c["SIGNED_FLOW_MIN"]):
        return _wait(f"Signed flow is incoherent ({signed_flow:.2f})")

    structure = bars[-range_bars - 1:-1]
    range_high = max(bar["high"] for bar in structure)
    range_low = min(bar["low"] for bar in structure)
    breakout = bars[-1]
    body = breakout["close"] - breakout["open"]
    bar_range = breakout["high"] - breakout["low"]
    if signed_flow > 0.0 and breakout["close"] > range_high and body > 0.0:
        side = 1
    elif signed_flow < 0.0 and breakout["close"] < range_low and body < 0.0:
        side = -1
    else:
        return _wait("No range break aligned with toxic signed flow")
    if bar_range <= 0.0:
        return _wait("Breakout bar range is zero")
    if abs(body) < bar_range * float(c["BREAK_BODY_MIN_FRACTION"]):
        return _wait("Breakout bar lacks directional efficiency")
    if abs(body) < atr * float(c["BREAK_BODY_MIN_ATR"]):
        return _wait("Breakout body is too small versus ATR")

    entry = round(breakout["close"], 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor((breakout["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((breakout["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Flow-break risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Flow-break risk too large versus price")

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
        "pattern": f"S254 {signal} VPIN Toxic-Flow Break {rr:g}R",
        "reason": (
            f"Efficient break aligned with toxic signed flow "
            f"(VPIN={vpin:.2f}, signed={signed_flow:.2f})"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
