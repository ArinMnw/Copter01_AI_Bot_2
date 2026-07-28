# -*- coding: utf-8 -*-
"""S176 - Median/MAD location-anomaly reclaim, optimized 10R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "LOCATION_WINDOW": 64,
    "ROBUST_Z_MIN": 2.60,
    "EXHAUSTION_BODY_MIN_ATR": 0.30,
    "EXHAUSTION_VOLUME_QUANTILE": 0.70,
    "RECLAIM_CLOSE_EDGE": 0.60,
    "RECLAIM_VOLUME_QUANTILE": 0.45,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.30,
    "MAX_RISK_PRICE_PCT": 0.32,
    "TP_RR": 10.00,
    "BE_RR": 1.18,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _median(values):
    ordered = sorted(float(value) for value in values)
    size = len(ordered)
    middle = size // 2
    return ordered[middle] if size % 2 else (ordered[middle - 1] + ordered[middle]) * 0.50


def detect_s176(rates, tf, dt_bkk, cfg):
    """Fade a robust close-location outlier only after a closed meanward reclaim."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(24, int(c["LOCATION_WINDOW"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < window + period + 4 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-2], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    history = bars[-window - 2:-2]
    closes = [bar["close"] for bar in history]
    median = _median(closes)
    mad = _median([abs(value - median) for value in closes])
    robust_scale = max(1.4826 * mad, atr * 0.10)

    exhaustion = bars[-2]
    reclaim = bars[-1]
    robust_z = (exhaustion["close"] - median) / robust_scale
    if abs(robust_z) < float(c["ROBUST_Z_MIN"]):
        return _wait(f"Close is not a robust location outlier (z={robust_z:.2f})")
    exhaustion_body = exhaustion["close"] - exhaustion["open"]
    exhaustion_range = exhaustion["high"] - exhaustion["low"]
    if (exhaustion_range <= 0.0
            or robust_z * exhaustion_body <= 0.0
            or abs(exhaustion_body) < atr * float(c["EXHAUSTION_BODY_MIN_ATR"])):
        return _wait("Location outlier lacks aligned exhaustion body")
    volume_min = _quantile(
        [bar["tick_volume"] for bar in history], c["EXHAUSTION_VOLUME_QUANTILE"]
    )
    if exhaustion["tick_volume"] < volume_min:
        return _wait("Location outlier lacks exhaustion volume")

    reclaim_range = reclaim["high"] - reclaim["low"]
    if reclaim_range <= 0.0:
        return _wait("Reclaim range is zero")
    reclaim_location = (reclaim["close"] - reclaim["low"]) / reclaim_range
    exhaustion_midpoint = (exhaustion["open"] + exhaustion["close"]) * 0.50
    reclaim_volume_min = _quantile(
        [bar["tick_volume"] for bar in history], c["RECLAIM_VOLUME_QUANTILE"]
    )
    edge = float(c["RECLAIM_CLOSE_EDGE"])
    if robust_z < 0.0:
        side = 1
        confirmed = (reclaim["close"] > reclaim["open"]
                     and reclaim["close"] > exhaustion_midpoint
                     and reclaim_location >= edge)
    else:
        side = -1
        confirmed = (reclaim["close"] < reclaim["open"]
                     and reclaim["close"] < exhaustion_midpoint
                     and reclaim_location <= 1.0 - edge)
    if not confirmed or reclaim["tick_volume"] < reclaim_volume_min:
        return _wait("Location outlier lacks confirmed meanward reclaim")

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
        return _wait(f"Location-reclaim risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Location-reclaim risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S176 {signal} Robust Location Reclaim {rr:g}R",
        "reason": (f"Median/MAD z={robust_z:.2f}; high-volume location anomaly "
                   "closed a meanward reclaim"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
