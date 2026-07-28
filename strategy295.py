# -*- coding: utf-8 -*-
"""S295 - Sup-Chow adaptive slope-break release, 10R.

S294 uses one preselected regression split.  S295 searches a small,
predeclared grid of admissible recent breakpoints and retains the split with
the largest Chow-style F statistic.  The signal therefore adapts to when the
closed-bar slope regime actually changed, while the release candle and
event-extreme stop preserve execution realism.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy294 import _chow_slope_break


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "REGRESSION_WINDOW": 72,
    "RECENT_SEGMENT_MIN": 16,
    "RECENT_SEGMENT_MAX": 32,
    "SPLIT_STEP": 4,
    "SUP_CHOW_F_MIN": 5.0,
    "RECENT_SLOPE_ATR_MIN": 0.025,
    "SLOPE_CHANGE_ATR_MIN": 0.020,
    "SLOPE_ACCELERATION_MIN": 1.05,
    "RELEASE_BODY_ATR_MIN": 0.55,
    "RELEASE_RANGE_ATR_MIN": 0.75,
    "RELEASE_CLOSE_FRACTION": 0.62,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 10.0,
    "BE_RR": 1.0,
    "CANCEL_BARS": 3,
}


def _sup_chow_slope_break(
    values,
    recent_min,
    recent_max,
    split_step,
):
    """Return the strongest admissible (F, old slope, new slope, split)."""
    n = len(values)
    if recent_min < 3 or recent_max < recent_min or split_step < 1:
        return None
    candidates = []
    for recent_length in range(recent_min, recent_max + 1, split_step):
        split = n - recent_length
        if split < 3:
            continue
        result = _chow_slope_break(values, split)
        if result is not None:
            candidates.append((*result, split))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])


def detect_s295(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a release aligned with the strongest recent OLS slope break."""
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
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if recent_max > regression_window - 3:
        return _wait("Recent segment leaves too little baseline history")
    required = max(regression_window + 3, period + 5)
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
        return _wait(f"No significant adaptive slope break (F={f_stat:.2f})")
    if abs(recent_slope) / atr < float(c["RECENT_SLOPE_ATR_MIN"]):
        return _wait("Adaptive recent slope is too flat")
    if abs(recent_slope - old_slope) / atr < float(c["SLOPE_CHANGE_ATR_MIN"]):
        return _wait("Adaptive slope change is too small versus ATR")
    if (
        abs(recent_slope)
        < abs(old_slope) * float(c["SLOPE_ACCELERATION_MIN"])
    ):
        return _wait("Adaptive recent slope has not accelerated")

    regime_side = 1 if recent_slope > 0.0 else -1
    event = bars[-1]
    event_body = event["close"] - event["open"]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Release candle has zero range")
    if event_body * regime_side <= 0.0:
        return _wait("Release candle opposes the adaptive slope")
    if abs(event_body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if event_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    if regime_side > 0:
        signal, side = "BUY", 1
        close_location = (event["close"] - event["low"]) / event_range
    else:
        signal, side = "SELL", -1
        close_location = (event["high"] - event["close"]) / event_range
    if close_location < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Release candle closes without directional control")
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
        return _wait(f"Release risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Release risk too large versus price")

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
        "pattern": f"S295 {signal} Sup-Chow Break {rr:g}R",
        "reason": (
            f"Adaptive OLS break F={f_stat:.6f}, recent={recent_length}, "
            f"old slope={old_slope:.4f}, recent slope={recent_slope:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
