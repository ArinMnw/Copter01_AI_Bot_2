# -*- coding: utf-8 -*-
"""S293 - Ljung-Box anti-persistence failed-sweep reclaim, 25.1R.

S292 follows positive multi-lag return dependence.  S293 tests the separate
anti-persistent regime: the Ljung-Box statistic must show joint serial
dependence while the weighted autocorrelation is negative.  A closed
liquidity sweep must then reclaim a recent extreme before the next-open fade.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy292 import _ljung_box_persistence


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "RETURN_LOOKBACK": 64,
    "LJUNG_BOX_LAGS": 5,
    "LJUNG_BOX_Z_MIN": 0.50,
    "WEIGHTED_AUTOCORR_MAX": -0.030,
    "SWEEP_LOOKBACK": 16,
    "SWEEP_MIN_ATR": 0.03,
    "RECLAIM_MIN_ATR": 0.02,
    "EVENT_RANGE_ATR_MIN": 0.75,
    "REJECTION_WICK_FRACTION_MIN": 0.28,
    "CLOSE_CONTROL_MIN": 0.55,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    "TP_RR": 25.10,
    "BE_RR": 0.875,
    "CANCEL_BARS": 3,
}


def detect_s293(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a closed failed sweep in significant anti-persistent returns."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        return_lookback = max(16, int(c["RETURN_LOOKBACK"]))
        lags = max(1, int(c["LJUNG_BOX_LAGS"]))
        sweep_lookback = max(3, int(c["SWEEP_LOOKBACK"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(return_lookback + 4, sweep_lookback + 4, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [bar["close"] for bar in bars[-return_lookback - 2:-1]]
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
        dependence = _ljung_box_persistence(returns, lags)
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
    if dependence is None:
        return _wait("Ljung-Box dependence statistic is unavailable")
    q_stat, zscore, weighted_rho = dependence
    if zscore < float(c["LJUNG_BOX_Z_MIN"]):
        return _wait(f"Serial dependence is insignificant (z={zscore:.2f})")
    if weighted_rho > float(c["WEIGHTED_AUTOCORR_MAX"]):
        return _wait(f"Multi-lag dependence is not anti-persistent ({weighted_rho:.3f})")

    event = bars[-1]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Sweep candle has zero range")
    if event_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Sweep range is too small versus ATR")
    history = bars[-sweep_lookback - 1:-1]
    prior_high = max(bar["high"] for bar in history)
    prior_low = min(bar["low"] for bar in history)
    sweep_floor = atr * float(c["SWEEP_MIN_ATR"])
    reclaim_floor = atr * float(c["RECLAIM_MIN_ATR"])
    swept_low = (
        event["low"] <= prior_low - sweep_floor
        and event["close"] >= prior_low + reclaim_floor
    )
    swept_high = (
        event["high"] >= prior_high + sweep_floor
        and event["close"] <= prior_high - reclaim_floor
    )
    if swept_low == swept_high:
        return _wait("No unique closed failed sweep")
    if swept_low:
        signal, side = "BUY", 1
        rejection_wick = min(event["open"], event["close"]) - event["low"]
        close_control = (event["close"] - event["low"]) / event_range
        swept_level = prior_low
    else:
        signal, side = "SELL", -1
        rejection_wick = event["high"] - max(event["open"], event["close"])
        close_control = (event["high"] - event["close"]) / event_range
        swept_level = prior_high
    if rejection_wick / event_range < float(c["REJECTION_WICK_FRACTION_MIN"]):
        return _wait("Failed sweep lacks rejection wick")
    if close_control < float(c["CLOSE_CONTROL_MIN"]):
        return _wait("Failed sweep closes without reversal control")
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
        return _wait(f"Sweep risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Sweep risk too large versus price")

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
        "pattern": f"S293 {signal} Ljung-Box Anti Sweep {rr:g}R",
        "reason": (
            f"Failed sweep/reclaim of {swept_level:.2f} in anti-persistence "
            f"Q={q_stat:.2f}, z={zscore:.2f}, rho={weighted_rho:.3f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
