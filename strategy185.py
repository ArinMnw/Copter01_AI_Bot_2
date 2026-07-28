# -*- coding: utf-8 -*-
"""S185 - CLV-pressure confirmed structural-break pullback, 7R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile
from strategy184 import _clv


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "PRESSURE_WINDOW": 64,
    "IMPULSE_SPAN": 8,
    "STRUCTURE_LOOKBACK": 16,
    "MIN_DISPLACEMENT_ATR": 0.90,
    "MIN_ALIGNED_PRESSURE": 0.18,
    "BREAK_BUFFER_ATR": 0.02,
    "BREAK_VOLUME_QUANTILE": 0.55,
    "PULLBACK_MAX_RETRACE": 0.55,
    "PULLBACK_VOLUME_MAX_QUANTILE": 0.75,
    "ENTRY_RANGE_FRACTION": 0.40,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.35,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s185(rates, tf, dt_bkk, cfg):
    """Continue a structural break whose displacement is confirmed by CLV pressure."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(24, int(c["PRESSURE_WINDOW"]))
        span = max(4, int(c["IMPULSE_SPAN"]))
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
    breakout = bars[-2]
    pullback = bars[-1]
    impulse = bars[-span - 1:-1]
    volume_sum = sum(max(bar["tick_volume"], 0.0) for bar in impulse)
    if volume_sum <= 0.0:
        return _wait("Impulse volume is zero")
    pressure = sum(_clv(bar) * max(bar["tick_volume"], 0.0)
                   for bar in impulse) / volume_sum
    displacement = breakout["close"] - impulse[0]["open"]
    displacement_min = atr * float(c["MIN_DISPLACEMENT_ATR"])
    pressure_min = float(c["MIN_ALIGNED_PRESSURE"])
    if displacement >= displacement_min and pressure >= pressure_min:
        side = 1
    elif displacement <= -displacement_min and pressure <= -pressure_min:
        side = -1
    else:
        return _wait(
            f"No aligned CLV impulse (move={displacement / atr:.2f} ATR, "
            f"pressure={pressure:.2f})"
        )

    structure = bars[-structure_lookback - 2:-2]
    break_buffer = atr * float(c["BREAK_BUFFER_ATR"])
    if side > 0 and breakout["high"] <= max(bar["high"] for bar in structure) + break_buffer:
        return _wait("Bullish CLV impulse did not break structural high")
    if side < 0 and breakout["low"] >= min(bar["low"] for bar in structure) - break_buffer:
        return _wait("Bearish CLV impulse did not break structural low")
    break_volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["BREAK_VOLUME_QUANTILE"]
    )
    if breakout["tick_volume"] < break_volume_floor:
        return _wait("Structural break lacks participation volume")

    breakout_range = breakout["high"] - breakout["low"]
    pullback_range = pullback["high"] - pullback["low"]
    if breakout_range <= 0.0 or pullback_range <= 0.0:
        return _wait("Breakout or pullback range is zero")
    retrace_max = float(c["PULLBACK_MAX_RETRACE"])
    pullback_volume_ceiling = _quantile(
        [bar["tick_volume"] for bar in history], c["PULLBACK_VOLUME_MAX_QUANTILE"]
    )
    if pullback["tick_volume"] > pullback_volume_ceiling:
        return _wait("Counter-pullback volume is too aggressive")
    if side > 0:
        retrace = (breakout["high"] - pullback["low"]) / breakout_range
        confirmed = (pullback["close"] < pullback["open"]
                     and pullback["close"] > breakout["low"] + breakout_range * 0.50
                     and 0.0 < retrace <= retrace_max)
    else:
        retrace = (pullback["high"] - breakout["low"]) / breakout_range
        confirmed = (pullback["close"] > pullback["open"]
                     and pullback["close"] < breakout["high"] - breakout_range * 0.50
                     and 0.0 < retrace <= retrace_max)
    if not confirmed:
        return _wait(f"No shallow counter-pullback ({retrace:.2f})")

    fraction = float(c["ENTRY_RANGE_FRACTION"])
    if side > 0:
        entry = pullback["low"] + fraction * pullback_range
        if entry >= pullback["close"]:
            return _wait("BUY limit is not below pullback close")
        sl = min(breakout["low"], pullback["low"]) - atr * float(c["SL_BUFFER_ATR"])
        entry = round(entry, 2)
        sl = math.floor((sl + 1e-12) * 100.0) / 100.0
    else:
        entry = pullback["high"] - fraction * pullback_range
        if entry <= pullback["close"]:
            return _wait("SELL limit is not above pullback close")
        sl = max(breakout["high"], pullback["high"]) + atr * float(c["SL_BUFFER_ATR"])
        entry = round(entry, 2)
        sl = math.ceil((sl - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"CLV-pullback risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"CLV-pullback risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S185 {signal} CLV Break Pullback {rr:g}R",
        "reason": (f"Aligned displacement={displacement / atr:.2f} ATR and "
                   f"CLV pressure={pressure:.2f}; shallow retrace={retrace:.2f}"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
