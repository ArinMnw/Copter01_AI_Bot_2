# -*- coding: utf-8 -*-
"""S298 - Jarque-Bera asymmetric-tail exhaustion reclaim, SELL 24R.

S297 follows a release in the direction of a non-Gaussian skew tail.  S298
tests the complementary exhaustion hypothesis: price extends in the skew
direction, sweeps a recent extreme, then closes back through it.  The failed
tail extension is faded at the next open with the event extreme as the stop.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy297 import _jarque_bera_shape


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "RETURN_LOOKBACK": 68,
    "JARQUE_BERA_MIN": 0.25,
    "ABS_SKEW_MIN": 0.10,
    "SWEEP_LOOKBACK": 14,
    "SWEEP_MIN_ATR": 0.03,
    "RECLAIM_MIN_ATR": 0.02,
    "EVENT_RANGE_ATR_MIN": 0.75,
    "REJECTION_WICK_FRACTION_MIN": 0.45,
    "CLOSE_CONTROL_MIN": 0.55,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    "TP_RR": 24.0,
    "BE_RR": 1.575,
    "CANCEL_BARS": 3,
}


def detect_s298(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a closed failed extension in an asymmetric return-tail regime."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        return_lookback = max(8, int(c["RETURN_LOOKBACK"]))
        sweep_lookback = max(3, int(c["SWEEP_LOOKBACK"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(return_lookback + 4, sweep_lookback + 3, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [
            bar["close"] for bar in bars[-return_lookback - 2:-1]
        ]
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
        shape = _jarque_bera_shape(returns)
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
    if shape is None:
        return _wait("Jarque-Bera shape statistic is unavailable")
    jb_stat, skewness, excess_kurtosis = shape
    if jb_stat < float(c["JARQUE_BERA_MIN"]):
        return _wait(f"Return shape is not non-Gaussian (JB={jb_stat:.2f})")
    if abs(skewness) < float(c["ABS_SKEW_MIN"]):
        return _wait(f"Non-Gaussian regime lacks tail direction ({skewness:.2f})")

    event = bars[-1]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Tail-rejection candle has zero range")
    if event_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Tail-rejection range is too small versus ATR")
    history = bars[-sweep_lookback - 1:-1]
    prior_high = max(bar["high"] for bar in history)
    prior_low = min(bar["low"] for bar in history)
    sweep_floor = atr * float(c["SWEEP_MIN_ATR"])
    reclaim_floor = atr * float(c["RECLAIM_MIN_ATR"])

    if skewness > 0.0:
        if not (
            event["high"] >= prior_high + sweep_floor
            and event["close"] <= prior_high - reclaim_floor
            and event["close"] < event["open"]
        ):
            return _wait("Positive tail has no closed upside exhaustion")
        signal, side = "SELL", -1
        swept_level = prior_high
        rejection_wick = event["high"] - max(event["open"], event["close"])
        close_control = (event["high"] - event["close"]) / event_range
    else:
        if not (
            event["low"] <= prior_low - sweep_floor
            and event["close"] >= prior_low + reclaim_floor
            and event["close"] > event["open"]
        ):
            return _wait("Negative tail has no closed downside exhaustion")
        signal, side = "BUY", 1
        swept_level = prior_low
        rejection_wick = min(event["open"], event["close"]) - event["low"]
        close_control = (event["close"] - event["low"]) / event_range
    if rejection_wick / event_range < float(c["REJECTION_WICK_FRACTION_MIN"]):
        return _wait("Failed tail extension lacks rejection wick")
    if close_control < float(c["CLOSE_CONTROL_MIN"]):
        return _wait("Failed tail extension closes without reversal control")
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
        return _wait(f"Tail-rejection risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Tail-rejection risk too large versus price")

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
        "pattern": f"S298 {signal} JB Tail Exhaustion {rr:g}R",
        "reason": (
            f"Rejected {swept_level:.2f} in non-Gaussian tail "
            f"JB={jb_stat:.2f}, skew={skewness:.3f}, "
            f"excess kurtosis={excess_kurtosis:.2f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
