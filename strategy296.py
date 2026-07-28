# -*- coding: utf-8 -*-
"""S296 - Sup-Chow slope-break rejection fade, SELL 26.8R.

S295 follows the strongest adaptive slope break.  S296 tests the opposite
hypothesis: a statistically strong new slope becomes crowded, sweeps a recent
extreme, then closes back through that level.  The closed failed extension is
faded at the next open with the sweep extreme as a volatility-buffered stop.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy295 import _sup_chow_slope_break


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "REGRESSION_WINDOW": 72,
    "RECENT_SEGMENT_MIN": 16,
    "RECENT_SEGMENT_MAX": 32,
    "SPLIT_STEP": 4,
    "SUP_CHOW_F_MIN": 10.0,
    "RECENT_SLOPE_ATR_MIN": 0.025,
    "SLOPE_CHANGE_ATR_MIN": 0.020,
    "SWEEP_LOOKBACK": 16,
    "SWEEP_MIN_ATR": 0.03,
    "RECLAIM_MIN_ATR": 0.02,
    "EVENT_RANGE_ATR_MIN": 0.75,
    "REJECTION_WICK_FRACTION_MIN": 0.30,
    "CLOSE_CONTROL_MIN": 0.55,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    "TP_RR": 26.8,
    "BE_RR": 0.3125,
    "CANCEL_BARS": 3,
}


def detect_s296(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a closed extreme rejection against a strong adaptive slope."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        regression_window = max(12, int(c["REGRESSION_WINDOW"]))
        recent_min = max(3, int(c["RECENT_SEGMENT_MIN"]))
        recent_max = max(recent_min, int(c["RECENT_SEGMENT_MAX"]))
        split_step = max(1, int(c["SPLIT_STEP"]))
        sweep_lookback = max(3, int(c["SWEEP_LOOKBACK"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if recent_max > regression_window - 3:
        return _wait("Recent segment leaves too little baseline history")
    required = max(regression_window + 3, sweep_lookback + 3, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [
            bar["close"] for bar in bars[-regression_window - 1:-1]
        ]
        structural_break = _sup_chow_slope_break(
            closes,
            recent_min,
            recent_max,
            split_step,
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
    if structural_break is None:
        return _wait("Sup-Chow slope-break statistic is unavailable")
    f_stat, old_slope, recent_slope, split = structural_break
    if f_stat < float(c["SUP_CHOW_F_MIN"]):
        return _wait(f"Adaptive slope break is too weak (F={f_stat:.2f})")
    if abs(recent_slope) / atr < float(c["RECENT_SLOPE_ATR_MIN"]):
        return _wait("Adaptive recent slope is too flat")
    if abs(recent_slope - old_slope) / atr < float(c["SLOPE_CHANGE_ATR_MIN"]):
        return _wait("Adaptive slope change is too small versus ATR")

    trend_side = 1 if recent_slope > 0.0 else -1
    event = bars[-1]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Rejection candle has zero range")
    if event_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Rejection range is too small versus ATR")
    history = bars[-sweep_lookback - 1:-1]
    prior_high = max(bar["high"] for bar in history)
    prior_low = min(bar["low"] for bar in history)
    sweep_floor = atr * float(c["SWEEP_MIN_ATR"])
    reclaim_floor = atr * float(c["RECLAIM_MIN_ATR"])

    if trend_side > 0:
        if not (
            event["high"] >= prior_high + sweep_floor
            and event["close"] <= prior_high - reclaim_floor
            and event["close"] < event["open"]
        ):
            return _wait("Rising regime has no closed upside rejection")
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
            return _wait("Falling regime has no closed downside rejection")
        signal, side = "BUY", 1
        swept_level = prior_low
        rejection_wick = min(event["open"], event["close"]) - event["low"]
        close_control = (event["close"] - event["low"]) / event_range
    if rejection_wick / event_range < float(c["REJECTION_WICK_FRACTION_MIN"]):
        return _wait("Failed extension lacks rejection wick")
    if close_control < float(c["CLOSE_CONTROL_MIN"]):
        return _wait("Failed extension closes without reversal control")
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
    recent_length = regression_window - split
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S296 {signal} Sup-Chow Rejection {rr:g}R",
        "reason": (
            f"Rejected {swept_level:.2f} against adaptive slope "
            f"F={f_stat:.2f}, recent={recent_length}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
