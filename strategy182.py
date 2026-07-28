# -*- coding: utf-8 -*-
"""S182 - Signed-volume impact-residual reclaim with a 7R target."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "IMPACT_WINDOW": 64,
    "IMPACT_RESIDUAL_Z_MIN": 2.20,
    "EXHAUSTION_BODY_MIN_ATR": 0.28,
    "EXHAUSTION_VOLUME_QUANTILE": 0.55,
    "RECLAIM_CLOSE_EDGE": 0.58,
    "RECLAIM_VOLUME_QUANTILE": 0.35,
    "RECLAIM_RESIDUAL_Z_MIN": 0.10,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.35,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _signed_volume(bar, volume_scale):
    bar_range = bar["high"] - bar["low"]
    if bar_range <= 0.0:
        return 0.0
    pressure = (bar["close"] - bar["open"]) / bar_range
    return pressure * bar["tick_volume"] / max(volume_scale, 1.0)


def detect_s182(rates, tf, dt_bkk, cfg):
    """Fade an abnormal return unexplained by its signed-volume price impact."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(24, int(c["IMPACT_WINDOW"]))
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
    volume_scale = _quantile([bar["tick_volume"] for bar in history], 0.50)
    x_values = []
    returns = []
    for index in range(1, len(history)):
        x_values.append(_signed_volume(history[index], volume_scale))
        returns.append(history[index]["close"] - history[index - 1]["close"])
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(returns) / len(returns)
    denominator = sum((value - x_mean) ** 2 for value in x_values)
    slope = sum((x - x_mean) * (y - y_mean)
                for x, y in zip(x_values, returns)) / max(denominator, 1e-12)
    intercept = y_mean - slope * x_mean
    residuals = [y - (intercept + slope * x)
                 for x, y in zip(x_values, returns)]
    residual_scale = max(
        math.sqrt(sum(value * value for value in residuals) / max(len(residuals) - 2, 1)),
        atr * 0.08,
    )

    exhaustion = bars[-2]
    reclaim = bars[-1]
    exhaustion_x = _signed_volume(exhaustion, volume_scale)
    exhaustion_return = exhaustion["close"] - history[-1]["close"]
    exhaustion_residual = exhaustion_return - (intercept + slope * exhaustion_x)
    exhaustion_z = exhaustion_residual / residual_scale
    if abs(exhaustion_z) < float(c["IMPACT_RESIDUAL_Z_MIN"]):
        return _wait(f"Return is explained by signed-volume impact (z={exhaustion_z:.2f})")
    side = 1 if exhaustion_residual < 0.0 else -1
    exhaustion_body = exhaustion["close"] - exhaustion["open"]
    exhaustion_range = exhaustion["high"] - exhaustion["low"]
    if (exhaustion_range <= 0.0
            or exhaustion_residual * exhaustion_body <= 0.0
            or abs(exhaustion_body) < atr * float(c["EXHAUSTION_BODY_MIN_ATR"])):
        return _wait("Impact residual lacks aligned exhaustion body")
    exhaustion_volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["EXHAUSTION_VOLUME_QUANTILE"]
    )
    if exhaustion["tick_volume"] < exhaustion_volume_floor:
        return _wait("Impact residual lacks participation volume")

    reclaim_range = reclaim["high"] - reclaim["low"]
    if reclaim_range <= 0.0:
        return _wait("Reclaim range is zero")
    reclaim_x = _signed_volume(reclaim, volume_scale)
    reclaim_return = reclaim["close"] - exhaustion["close"]
    reclaim_residual = reclaim_return - (intercept + slope * reclaim_x)
    reclaim_z = reclaim_residual / residual_scale
    reclaim_location = (reclaim["close"] - reclaim["low"]) / reclaim_range
    exhaustion_midpoint = (exhaustion["open"] + exhaustion["close"]) * 0.50
    reclaim_volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["RECLAIM_VOLUME_QUANTILE"]
    )
    edge = float(c["RECLAIM_CLOSE_EDGE"])
    residual_min = float(c["RECLAIM_RESIDUAL_Z_MIN"])
    if side > 0:
        confirmed = (reclaim["close"] > reclaim["open"]
                     and reclaim["close"] > exhaustion_midpoint
                     and reclaim_location >= edge
                     and reclaim_z >= residual_min)
    else:
        confirmed = (reclaim["close"] < reclaim["open"]
                     and reclaim["close"] < exhaustion_midpoint
                     and reclaim_location <= 1.0 - edge
                     and reclaim_z <= -residual_min)
    if not confirmed or reclaim["tick_volume"] < reclaim_volume_floor:
        return _wait("Impact anomaly lacks opposite residual reclaim")

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
        return _wait(f"Impact-reclaim risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Impact-reclaim risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S182 {signal} Impact Residual {rr:g}R",
        "reason": (f"Signed-volume impact residual z={exhaustion_z:.2f}; "
                   f"opposite reclaim z={reclaim_z:.2f}"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
