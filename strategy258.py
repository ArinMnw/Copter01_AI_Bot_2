# -*- coding: utf-8 -*-
"""S258 - Local-linear-trend Kalman innovation fade, 28.1R.

S257's local-level fair value may label ordinary trend as an overshoot.  S258
uses a two-state Kalman model for level and slope, then fades only a fresh
standardized innovation that remains extreme after adaptive trend removal.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy232 import DEFAULT_CFG as S232_DEFAULT_CFG
from strategy232 import detect_s232


DEFAULT_CFG = {
    **S232_DEFAULT_CFG,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "KALMAN_LOOKBACK": 96,
    "LEVEL_NOISE_ATR": 0.05,
    "SLOPE_NOISE_ATR": 0.01,
    "MEASUREMENT_NOISE_ATR": 0.50,
    "INNOVATION_Z_MIN": 2.50,
    "TP_RR": 28.10,
    "BE_RR": 0.50,
}


def _local_trend_state(
    closes, level_variance, slope_variance, measurement_variance
):
    level = float(closes[0])
    slope = 0.0
    p00 = measurement_variance
    p01 = 0.0
    p11 = measurement_variance * 0.10
    last_zscore = 0.0
    for close in closes[1:]:
        predicted_level = level + slope
        a = p00 + 2.0 * p01 + p11 + level_variance
        b = p01 + p11
        d = p11 + slope_variance
        innovation_variance = a + measurement_variance
        if innovation_variance <= 0.0:
            return None
        innovation = float(close) - predicted_level
        last_zscore = innovation / math.sqrt(innovation_variance)
        gain_level = a / innovation_variance
        gain_slope = b / innovation_variance
        level = predicted_level + gain_level * innovation
        slope += gain_slope * innovation
        p00 = (1.0 - gain_level) * a
        p01 = (1.0 - gain_level) * b
        p11 = max(0.0, d - gain_slope * b)
    return level, slope, p00, p01, p11, last_zscore


def detect_s258(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a fresh trend-adjusted Kalman innovation overshoot."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(24, int(c["KALMAN_LOOKBACK"]))
        period = max(1, int(c["ATR_PERIOD"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(lookback + 3, period + 5)
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
    level_variance = (atr * float(c["LEVEL_NOISE_ATR"])) ** 2
    slope_variance = (atr * float(c["SLOPE_NOISE_ATR"])) ** 2
    measurement_variance = (atr * float(c["MEASUREMENT_NOISE_ATR"])) ** 2
    if min(level_variance, slope_variance, measurement_variance) <= 0.0:
        return _wait("Kalman noise variance is zero")

    closes = [bar["close"] for bar in bars[-lookback - 1:-1]]
    state = _local_trend_state(
        closes, level_variance, slope_variance, measurement_variance
    )
    if state is None:
        return _wait("Local-trend Kalman state is unavailable")
    level, slope, p00, p01, p11, previous_zscore = state
    predicted_level = level + slope
    predicted_variance = (
        p00 + 2.0 * p01 + p11 + level_variance
    )
    innovation_variance = predicted_variance + measurement_variance
    current_zscore = (
        bars[-1]["close"] - predicted_level
    ) / math.sqrt(innovation_variance)
    threshold = float(c["INNOVATION_Z_MIN"])
    if abs(previous_zscore) >= threshold or abs(current_zscore) < threshold:
        return _wait(
            f"No fresh trend-adjusted innovation crossing "
            f"(prev={previous_zscore:.2f}, current={current_zscore:.2f})"
        )
    original_side = "BUY" if current_zscore > 0.0 else "SELL"

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    original = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if original.get("signal") != original_side:
        return _wait("Trend-adjusted innovation lacks structural break")

    event = bars[-1]
    entry = round(event["close"], 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    if original_side == "BUY":
        signal, side = "SELL", -1
        sl = math.ceil((event["high"] + buffer - 1e-12) * 100.0) / 100.0
    else:
        signal, side = "BUY", 1
        sl = math.floor((event["low"] - buffer + 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Fade risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Fade risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Fade risk too large versus price")

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
        "pattern": f"S258 {signal} Trend-Kalman Overshoot Fade {rr:g}R",
        "reason": (
            f"Fade fresh local-linear-trend innovation "
            f"(z={current_zscore:.2f}, slope={slope:.3f})"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
