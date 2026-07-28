# -*- coding: utf-8 -*-
"""S180 - Trend-adjusted regression-residual reclaim with a 16R target."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "REGRESSION_WINDOW": 64,
    "RESIDUAL_Z_MIN": 2.30,
    "EXHAUSTION_BODY_MIN_ATR": 0.30,
    "EXHAUSTION_VOLUME_QUANTILE": 0.65,
    "RECLAIM_CLOSE_EDGE": 0.60,
    "RECLAIM_VOLUME_QUANTILE": 0.45,
    "MIN_RESIDUAL_CONTRACTION": 0.20,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.30,
    "MAX_RISK_PRICE_PCT": 0.32,
    "TP_RR": 16.00,
    "BE_RR": 0.75,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s180(rates, tf, dt_bkk, cfg):
    """Fade a regression-residual outlier after a closed residual contraction."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(24, int(c["REGRESSION_WINDOW"]))
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
    x_mean = (window - 1) * 0.50
    y_mean = sum(closes) / window
    denominator = sum((index - x_mean) ** 2 for index in range(window))
    slope = sum((index - x_mean) * (value - y_mean)
                for index, value in enumerate(closes)) / max(denominator, 1e-12)
    intercept = y_mean - slope * x_mean
    residuals = [value - (intercept + slope * index)
                 for index, value in enumerate(closes)]
    residual_scale = max(
        math.sqrt(sum(value * value for value in residuals) / max(window - 2, 1)),
        atr * 0.10,
    )

    exhaustion = bars[-2]
    reclaim = bars[-1]
    exhaustion_trend = intercept + slope * window
    reclaim_trend = intercept + slope * (window + 1)
    exhaustion_residual = exhaustion["close"] - exhaustion_trend
    reclaim_residual = reclaim["close"] - reclaim_trend
    residual_z = exhaustion_residual / residual_scale
    if abs(residual_z) < float(c["RESIDUAL_Z_MIN"]):
        return _wait(f"Close is not a trend-adjusted outlier (z={residual_z:.2f})")

    exhaustion_body = exhaustion["close"] - exhaustion["open"]
    exhaustion_range = exhaustion["high"] - exhaustion["low"]
    if (exhaustion_range <= 0.0
            or exhaustion_residual * exhaustion_body <= 0.0
            or abs(exhaustion_body) < atr * float(c["EXHAUSTION_BODY_MIN_ATR"])):
        return _wait("Residual outlier lacks aligned exhaustion body")
    exhaustion_volume_min = _quantile(
        [bar["tick_volume"] for bar in history], c["EXHAUSTION_VOLUME_QUANTILE"]
    )
    if exhaustion["tick_volume"] < exhaustion_volume_min:
        return _wait("Residual outlier lacks exhaustion volume")

    contraction = 1.0 - abs(reclaim_residual) / max(abs(exhaustion_residual), 1e-12)
    if contraction < float(c["MIN_RESIDUAL_CONTRACTION"]):
        return _wait(f"Residual did not contract enough ({contraction:.2f})")
    reclaim_range = reclaim["high"] - reclaim["low"]
    if reclaim_range <= 0.0:
        return _wait("Reclaim range is zero")
    reclaim_location = (reclaim["close"] - reclaim["low"]) / reclaim_range
    exhaustion_midpoint = (exhaustion["open"] + exhaustion["close"]) * 0.50
    reclaim_volume_min = _quantile(
        [bar["tick_volume"] for bar in history], c["RECLAIM_VOLUME_QUANTILE"]
    )
    edge = float(c["RECLAIM_CLOSE_EDGE"])
    if exhaustion_residual < 0.0:
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
        return _wait("Residual outlier lacks confirmed meanward reclaim")

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
        return _wait(f"Residual-reclaim risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Residual-reclaim risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S180 {signal} Regression Residual {rr:g}R",
        "reason": (f"Residual z={residual_z:.2f}, contraction={contraction:.2f}; "
                   "trend-adjusted anomaly reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
