# -*- coding: utf-8 -*-
"""S269 - Ornstein-Uhlenbeck residual snapback, 10R.

A rolling linear trend is removed from closed prices and the residual is fitted
as an AR(1) process, the discrete form of an Ornstein-Uhlenbeck process.  S269
trades only a fresh standardized residual excursion when the fitted process is
stationary, its half-life is practical for M5, and the event candle rejects the
extreme back toward equilibrium.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy232 import DEFAULT_CFG as S232_DEFAULT_CFG


DEFAULT_CFG = {
    **S232_DEFAULT_CFG,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "OU_LOOKBACK": 96,
    "RESIDUAL_Z_MIN": 2.25,
    "HALF_LIFE_MIN": 2.00,
    "HALF_LIFE_MAX": 20.00,
    "REJECTION_WICK_MIN": 0.15,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def _linear_residuals(values):
    size = len(values)
    mean_x = (size - 1.0) / 2.0
    mean_y = sum(values) / size
    denominator = sum((index - mean_x) ** 2 for index in range(size))
    if denominator <= 0.0:
        return None
    slope = sum(
        (index - mean_x) * (value - mean_y)
        for index, value in enumerate(values)
    ) / denominator
    intercept = mean_y - slope * mean_x
    residuals = [
        value - (intercept + slope * index)
        for index, value in enumerate(values)
    ]
    return residuals, slope


def _ar1_phi(values):
    previous = values[:-1]
    current = values[1:]
    mean_previous = sum(previous) / len(previous)
    mean_current = sum(current) / len(current)
    denominator = sum((value - mean_previous) ** 2 for value in previous)
    if denominator <= 0.0:
        return None
    return sum(
        (x_value - mean_previous) * (y_value - mean_current)
        for x_value, y_value in zip(previous, current)
    ) / denominator


def detect_s269(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a fresh stationary OU residual excursion after candle rejection."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(32, int(c["OU_LOOKBACK"]))
        threshold = float(c["RESIDUAL_Z_MIN"])
        half_life_min = float(c["HALF_LIFE_MIN"])
        half_life_max = float(c["HALF_LIFE_MAX"])
        period = max(1, int(c["ATR_PERIOD"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if threshold <= 0.0 or not 0.0 < half_life_min <= half_life_max:
        return _wait("Invalid OU parameters")
    required = max(lookback + 3, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")

    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [bar["close"] for bar in bars[-lookback:]]
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    fitted = _linear_residuals(closes)
    if fitted is None:
        return _wait("Linear detrending is degenerate")
    residuals, trend_slope = fitted
    phi = _ar1_phi(residuals[:-1])
    if phi is None or not 0.0 < phi < 1.0:
        return _wait(f"Residual is not stationary OU (phi={phi})")
    half_life = -math.log(2.0) / math.log(phi)
    if not half_life_min <= half_life <= half_life_max:
        return _wait(f"OU half-life outside range ({half_life:.1f} bars)")
    scale = statistics.pstdev(residuals[:-1])
    if scale <= 0.0:
        return _wait("OU residual scale is zero")
    previous_zscore = residuals[-2] / scale
    current_zscore = residuals[-1] / scale
    if abs(previous_zscore) >= threshold or abs(current_zscore) < threshold:
        return _wait(
            f"No fresh OU residual crossing "
            f"(prev={previous_zscore:.2f}, current={current_zscore:.2f})"
        )

    event = bars[-1]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Event candle has zero range")
    lower_wick = min(event["open"], event["close"]) - event["low"]
    upper_wick = event["high"] - max(event["open"], event["close"])
    wick_min = float(c["REJECTION_WICK_MIN"])
    if (
        current_zscore < 0.0
        and event["close"] > event["open"]
        and lower_wick / event_range >= wick_min
    ):
        signal, side = "BUY", 1
    elif (
        current_zscore > 0.0
        and event["close"] < event["open"]
        and upper_wick / event_range >= wick_min
    ):
        signal, side = "SELL", -1
    else:
        return _wait("OU excursion lacks rejection toward equilibrium")

    entry = round(event["close"], 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor((event["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"OU risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"OU risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("OU risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    if side > 0:
        tp = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
    else:
        tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S269 {signal} OU Residual Snapback {rr:g}R",
        "reason": (
            f"Fresh stationary residual excursion z={current_zscore:.2f}, "
            f"half-life={half_life:.1f}, trend={trend_slope:.3f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
