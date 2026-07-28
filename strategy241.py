# -*- coding: utf-8 -*-
"""S241 - Negative CLV-pressure downside sweep reclaim, 10R.

Persistent negative volume-weighted Close Location Value shows sell-side
auction pressure.  If price sweeps a recent range low but closes back inside
with a bullish rejection, the failed auction is treated as absorbed supply and
traded long with a stop below the sweep wick.
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
    "SWEEP_RANGE_BARS": 8,
    "PRESSURE_MODE": "negative",
    "MAX_CLV_PRESSURE": -0.18,
    "MIN_CLV_PRESSURE": 0.18,
    "MIN_SWEEP_ATR": 0.03,
    "MIN_CLOSE_RECLAIM_FRACTION": 0.20,
    "MIN_LOWER_WICK_FRACTION": 0.35,
    "MIN_BODY_ATR": 0.15,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s241(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Buy a reclaimed downside sweep after persistent negative CLV pressure."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        pressure_window = max(8, int(c["PRESSURE_WINDOW"]))
        range_bars = max(4, int(c["SWEEP_RANGE_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
        pressure_mode = str(c["PRESSURE_MODE"]).strip().lower()
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if pressure_mode not in ("negative", "positive"):
        return _wait(f"Invalid pressure mode: {pressure_mode}")
    required = max(period + 5, pressure_window + 3, range_bars + 3)
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

    history = bars[-pressure_window - 1:-1]
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
    if pressure_mode == "negative":
        if pressure > float(c["MAX_CLV_PRESSURE"]):
            return _wait(f"Negative CLV pressure is insufficient ({pressure:.2f})")
    elif pressure < float(c["MIN_CLV_PRESSURE"]):
        return _wait(f"Positive CLV pressure is insufficient ({pressure:.2f})")

    structure = bars[-range_bars - 1:-1]
    range_low = min(bar["low"] for bar in structure)
    reclaim = bars[-1]
    bar_range = reclaim["high"] - reclaim["low"]
    body = reclaim["close"] - reclaim["open"]
    if reclaim["low"] > range_low - atr * float(c["MIN_SWEEP_ATR"]):
        return _wait("No meaningful downside sweep")
    if reclaim["close"] <= range_low:
        return _wait("Downside sweep did not reclaim the range")
    if body <= 0.0 or abs(body) < atr * float(c["MIN_BODY_ATR"]):
        return _wait("Reclaim bar lacks bullish displacement")
    if bar_range <= 0.0:
        return _wait("Reclaim bar range is zero")
    reclaim_fraction = (reclaim["close"] - range_low) / bar_range
    lower_wick = min(reclaim["open"], reclaim["close"]) - reclaim["low"]
    if reclaim_fraction < float(c["MIN_CLOSE_RECLAIM_FRACTION"]):
        return _wait("Close reclaim is too shallow")
    if lower_wick < bar_range * float(c["MIN_LOWER_WICK_FRACTION"]):
        return _wait("Reclaim lacks a lower rejection wick")

    entry = round(reclaim["close"], 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    sl = math.floor((reclaim["low"] - buffer + 1e-12) * 100.0) / 100.0
    risk = entry - sl
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Sweep risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Sweep risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + rr * risk
    tp = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
    return {
        "signal": "BUY",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S241 BUY Negative-CLV Sweep Reclaim {rr:g}R",
        "reason": (
            f"Downside failed auction after negative CLV pressure "
            f"(pressure={pressure:.2f}, reclaim={reclaim_fraction:.2f})"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
