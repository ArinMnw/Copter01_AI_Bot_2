# -*- coding: utf-8 -*-
"""S294 - Chow-style structural slope-break release, BUY 21.1R.

The detector compares one pooled OLS trend with separate trends before and
after a fixed split.  A large reduction in residual error indicates that the
recent slope belongs to a different price regime.  It then requires a strong
closed release candle aligned with the new slope and uses that event's extreme
as a deliberately short stop.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "BASELINE_WINDOW": 40,
    "RECENT_WINDOW": 24,
    "CHOW_F_MIN": 2.00,
    "RECENT_SLOPE_ATR_MIN": 0.025,
    "SLOPE_CHANGE_ATR_MIN": 0.020,
    "SLOPE_ACCELERATION_MIN": 1.10,
    "RELEASE_BODY_ATR_MIN": 0.55,
    "RELEASE_RANGE_ATR_MIN": 0.75,
    "RELEASE_CLOSE_FRACTION": 0.62,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": False,
    "TP_RR": 21.1,
    "BE_RR": 0.525,
    "CANCEL_BARS": 3,
}


def _ols_line(values):
    """Return (intercept, slope, SSE) for finite equally spaced values."""
    n = len(values)
    if n < 2:
        return None
    try:
        ys = [float(value) for value in values]
    except (TypeError, ValueError, OverflowError):
        return None
    if any(not math.isfinite(value) for value in ys):
        return None
    x_mean = (n - 1) / 2.0
    y_mean = sum(ys) / n
    denominator = sum((index - x_mean) ** 2 for index in range(n))
    if denominator <= 0.0:
        return None
    slope = sum(
        (index - x_mean) * (value - y_mean)
        for index, value in enumerate(ys)
    ) / denominator
    intercept = y_mean - slope * x_mean
    sse = sum(
        (value - (intercept + slope * index)) ** 2
        for index, value in enumerate(ys)
    )
    return intercept, slope, max(0.0, sse)


def _chow_slope_break(values, split):
    """Return (F, old slope, recent slope) for a two-parameter Chow test."""
    n = len(values)
    if split < 3 or n - split < 3 or n <= 4:
        return None
    pooled = _ols_line(values)
    old = _ols_line(values[:split])
    recent = _ols_line(values[split:])
    if pooled is None or old is None or recent is None:
        return None
    separate_sse = old[2] + recent[2]
    denominator_df = n - 4
    if separate_sse <= 1e-18 or denominator_df <= 0:
        return None
    improvement = max(0.0, pooled[2] - separate_sse)
    f_stat = (improvement / 2.0) / (separate_sse / denominator_df)
    return f_stat, old[1], recent[1]


def detect_s294(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade an event release aligned with a statistically broken OLS slope."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_window = max(3, int(c["BASELINE_WINDOW"]))
        recent_window = max(3, int(c["RECENT_WINDOW"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    total_window = baseline_window + recent_window
    required = max(total_window + 3, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [
            bar["close"] for bar in bars[-total_window - 1:-1]
        ]
        structural_break = _chow_slope_break(closes, baseline_window)
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
        return _wait("Chow slope-break statistic is unavailable")
    f_stat, old_slope, recent_slope = structural_break
    if f_stat < float(c["CHOW_F_MIN"]):
        return _wait(f"No significant slope break (F={f_stat:.2f})")
    normalized_recent = abs(recent_slope) / atr
    normalized_change = abs(recent_slope - old_slope) / atr
    if normalized_recent < float(c["RECENT_SLOPE_ATR_MIN"]):
        return _wait("New regime slope is too flat")
    if normalized_change < float(c["SLOPE_CHANGE_ATR_MIN"]):
        return _wait("Slope change is too small versus ATR")
    acceleration_floor = abs(old_slope) * float(c["SLOPE_ACCELERATION_MIN"])
    if abs(recent_slope) < acceleration_floor:
        return _wait("New regime has not accelerated beyond the old slope")

    regime_side = 1 if recent_slope > 0.0 else -1
    event = bars[-1]
    event_body = event["close"] - event["open"]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Release candle has zero range")
    if event_body * regime_side <= 0.0:
        return _wait("Release candle opposes the new slope")
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
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S294 {signal} Chow Slope Break {rr:g}R",
        "reason": (
            f"OLS structural break F={f_stat:.2f}, old slope={old_slope:.4f}, "
            f"recent slope={recent_slope:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
