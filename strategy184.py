# -*- coding: utf-8 -*-
"""S184 - Volume-weighted close-location pressure divergence reclaim, 8.5R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "PRESSURE_WINDOW": 64,
    "DIVERGENCE_SPAN": 8,
    "STRUCTURE_LOOKBACK": 16,
    "MIN_DISPLACEMENT_ATR": 0.75,
    "MIN_OPPOSITE_PRESSURE": 0.08,
    "EXHAUSTION_VOLUME_QUANTILE": 0.55,
    "SWEEP_BUFFER_ATR": 0.01,
    "RECLAIM_CLOSE_EDGE": 0.58,
    "RECLAIM_VOLUME_QUANTILE": 0.35,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.35,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 8.50,
    "BE_RR": 0.52,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _clv(bar):
    bar_range = bar["high"] - bar["low"]
    if bar_range <= 0.0:
        return 0.0
    return (2.0 * bar["close"] - bar["high"] - bar["low"]) / bar_range


def detect_s184(rates, tf, dt_bkk, cfg):
    """Fade displacement opposed by volume-weighted intrabar close pressure."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(24, int(c["PRESSURE_WINDOW"]))
        span = max(4, int(c["DIVERGENCE_SPAN"]))
        structure_lookback = max(span, int(c["STRUCTURE_LOOKBACK"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(window + 4, structure_lookback + 4, period + 4)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-2], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    history = bars[-window - 2:-2]
    exhaustion = bars[-2]
    reclaim = bars[-1]
    impulse = bars[-span - 1:-1]
    volume_sum = sum(max(bar["tick_volume"], 0.0) for bar in impulse)
    if volume_sum <= 0.0:
        return _wait("Impulse volume is zero")
    pressure = sum(_clv(bar) * max(bar["tick_volume"], 0.0)
                   for bar in impulse) / volume_sum
    displacement = exhaustion["close"] - impulse[0]["open"]
    displacement_min = atr * float(c["MIN_DISPLACEMENT_ATR"])
    pressure_min = float(c["MIN_OPPOSITE_PRESSURE"])
    if displacement <= -displacement_min and pressure >= pressure_min:
        side = 1
    elif displacement >= displacement_min and pressure <= -pressure_min:
        side = -1
    else:
        return _wait(
            f"No CLV-pressure divergence (move={displacement / atr:.2f} ATR, "
            f"pressure={pressure:.2f})"
        )

    structure = bars[-structure_lookback - 2:-2]
    sweep_buffer = atr * float(c["SWEEP_BUFFER_ATR"])
    if side > 0 and exhaustion["low"] >= min(bar["low"] for bar in structure) - sweep_buffer:
        return _wait("Bullish pressure divergence did not sweep a structural low")
    if side < 0 and exhaustion["high"] <= max(bar["high"] for bar in structure) + sweep_buffer:
        return _wait("Bearish pressure divergence did not sweep a structural high")
    exhaustion_volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["EXHAUSTION_VOLUME_QUANTILE"]
    )
    if exhaustion["tick_volume"] < exhaustion_volume_floor:
        return _wait("CLV-pressure divergence lacks exhaustion volume")

    reclaim_range = reclaim["high"] - reclaim["low"]
    if reclaim_range <= 0.0:
        return _wait("Reclaim range is zero")
    reclaim_location = (reclaim["close"] - reclaim["low"]) / reclaim_range
    exhaustion_midpoint = (exhaustion["open"] + exhaustion["close"]) * 0.50
    reclaim_volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["RECLAIM_VOLUME_QUANTILE"]
    )
    edge = float(c["RECLAIM_CLOSE_EDGE"])
    if side > 0:
        confirmed = (reclaim["close"] > reclaim["open"]
                     and reclaim["close"] > exhaustion_midpoint
                     and reclaim_location >= edge)
    else:
        confirmed = (reclaim["close"] < reclaim["open"]
                     and reclaim["close"] < exhaustion_midpoint
                     and reclaim_location <= 1.0 - edge)
    if not confirmed or reclaim["tick_volume"] < reclaim_volume_floor:
        return _wait("CLV-pressure divergence lacks confirmed reclaim")

    fraction = float(c["ENTRY_RANGE_FRACTION"])
    if side > 0:
        entry = reclaim["high"] - fraction * reclaim_range
        if entry >= reclaim["close"]:
            return _wait("BUY limit is not below reclaim close")
        sl = min(exhaustion["low"], reclaim["low"]) - atr * float(c["SL_BUFFER_ATR"])
        entry = round(entry, 2)
        sl = math.floor((sl + 1e-12) * 100.0) / 100.0
    else:
        entry = reclaim["low"] + fraction * reclaim_range
        if entry <= reclaim["close"]:
            return _wait("SELL limit is not above reclaim close")
        sl = max(exhaustion["high"], reclaim["high"]) + atr * float(c["SL_BUFFER_ATR"])
        entry = round(entry, 2)
        sl = math.ceil((sl - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"CLV-reclaim risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"CLV-reclaim risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S184 {signal} CLV Pressure Divergence {rr:g}R",
        "reason": (f"Displacement={displacement / atr:.2f} ATR opposed by "
                   f"volume-weighted CLV pressure={pressure:.2f}; reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
