# -*- coding: utf-8 -*-
"""S291 - Wasserstein distribution-drift rejection fade, 10R.

S290 follows a robust return-distribution shift.  S291 tests the complementary
failure regime: after a statistically large signed drift, a closed rejection
candle must oppose that shift and leave a wick toward the exhausted side.
The next-open market entry fades the drift with an event-extreme stop.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy290 import _wasserstein_drift


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "BASELINE_WINDOW": 48,
    "RECENT_WINDOW": 16,
    "WASSERSTEIN_MAD_MIN": 0.625,
    "MEDIAN_SHIFT_MAD_MIN": 0.8375,
    "REJECTION_BODY_ATR_MIN": 0.40,
    "REJECTION_RANGE_ATR_MIN": 0.80,
    "REJECTION_CLOSE_FRACTION": 0.62,
    "DRIFT_SIDE_WICK_FRACTION_MIN": 0.18,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s291(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a closed rejection of a robust return-distribution drift."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_window = max(8, int(c["BASELINE_WINDOW"]))
        recent_window = max(4, int(c["RECENT_WINDOW"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    history_returns = baseline_window + recent_window
    required = max(history_returns + 4, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [bar["close"] for bar in bars[-history_returns - 2:-1]]
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
        drift = _wasserstein_drift(
            returns[:baseline_window],
            returns[baseline_window:],
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        ZeroDivisionError,
        AttributeError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    if drift is None:
        return _wait("Return-distribution drift is unavailable")
    normalized_w1, normalized_shift = drift
    if normalized_w1 < float(c["WASSERSTEIN_MAD_MIN"]):
        return _wait(f"Distribution drift is too small ({normalized_w1:.2f} MAD)")
    if abs(normalized_shift) < float(c["MEDIAN_SHIFT_MAD_MIN"]):
        return _wait(f"Median drift is too small ({normalized_shift:.2f} MAD)")
    drift_side = 1 if normalized_shift > 0.0 else -1

    event = bars[-1]
    event_body = event["close"] - event["open"]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Rejection candle has zero range")
    if abs(event_body) < atr * float(c["REJECTION_BODY_ATR_MIN"]):
        return _wait("Rejection body is too small versus ATR")
    if event_range < atr * float(c["REJECTION_RANGE_ATR_MIN"]):
        return _wait("Rejection range is too small versus ATR")
    if event_body * drift_side >= 0.0:
        return _wait("Candle has not rejected the distribution drift")
    if drift_side > 0:
        signal, side = "SELL", -1
        close_location = (event["high"] - event["close"]) / event_range
        drift_wick = event["high"] - max(event["open"], event["close"])
    else:
        signal, side = "BUY", 1
        close_location = (event["close"] - event["low"]) / event_range
        drift_wick = min(event["open"], event["close"]) - event["low"]
    if close_location < float(c["REJECTION_CLOSE_FRACTION"]):
        return _wait("Rejection candle closes without reversal control")
    if drift_wick / event_range < float(c["DRIFT_SIDE_WICK_FRACTION_MIN"]):
        return _wait("Rejection lacks a wick toward the exhausted drift")
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled by direction-survival filter")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled by direction-survival filter")

    entry = round(event["close"], 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor((event["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Rejection risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Rejection risk too large versus price")

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
        "pattern": f"S291 {signal} Wasserstein Drift Fade {rr:g}R",
        "reason": (
            f"Rejected return-distribution drift {normalized_w1:.2f} MAD "
            f"with signed median shift {normalized_shift:+.2f} MAD"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
