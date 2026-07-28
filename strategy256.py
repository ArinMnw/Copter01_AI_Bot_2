# -*- coding: utf-8 -*-
"""S256 - Adaptive Kalman-innovation structural breakout, 10R.

A local-level Kalman filter estimates latent fair value and uncertainty from
closed prices.  A fresh standardized innovation crossing must align with an
efficient range break during the US liquidity window.
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
    "PROCESS_NOISE_ATR": 0.10,
    "MEASUREMENT_NOISE_ATR": 0.50,
    "INNOVATION_Z_MIN": 2.50,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def _kalman_state(closes, process_variance, measurement_variance):
    state = float(closes[0])
    variance = measurement_variance
    last_zscore = 0.0
    for close in closes[1:]:
        predicted_variance = variance + process_variance
        innovation = float(close) - state
        innovation_variance = predicted_variance + measurement_variance
        if innovation_variance <= 0.0:
            return None
        last_zscore = innovation / math.sqrt(innovation_variance)
        gain = predicted_variance / innovation_variance
        state += gain * innovation
        variance = (1.0 - gain) * predicted_variance
    return state, variance, last_zscore


def detect_s256(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a fresh Kalman innovation crossing with range-break confirmation."""
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
    process_variance = (atr * float(c["PROCESS_NOISE_ATR"])) ** 2
    measurement_variance = (atr * float(c["MEASUREMENT_NOISE_ATR"])) ** 2
    if process_variance <= 0.0 or measurement_variance <= 0.0:
        return _wait("Kalman noise variance is zero")

    closes = [bar["close"] for bar in bars[-lookback - 1:-1]]
    result = _kalman_state(closes, process_variance, measurement_variance)
    if result is None:
        return _wait("Kalman state is unavailable")
    state, variance, previous_zscore = result
    predicted_variance = variance + process_variance
    innovation_variance = predicted_variance + measurement_variance
    current_zscore = (bars[-1]["close"] - state) / math.sqrt(
        innovation_variance
    )
    threshold = float(c["INNOVATION_Z_MIN"])
    if abs(previous_zscore) >= threshold or abs(current_zscore) < threshold:
        return _wait(
            f"No fresh Kalman innovation crossing "
            f"(prev={previous_zscore:.2f}, current={current_zscore:.2f})"
        )
    expected_side = "BUY" if current_zscore > 0.0 else "SELL"

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    signal = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if signal.get("signal") != expected_side:
        return _wait("Kalman innovation does not align with a structural break")
    rr = max(7.0, float(c["TP_RR"]))
    signal = dict(signal)
    signal["pattern"] = f"S256 {expected_side} Kalman-Innovation Break {rr:g}R"
    signal["reason"] = (
        f"Fresh adaptive fair-value innovation with structural break "
        f"(z={current_zscore:.2f})"
    )
    return signal
