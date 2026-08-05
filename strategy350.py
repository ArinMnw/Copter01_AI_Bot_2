# -*- coding: utf-8 -*-
"""S350 - Volume-weighted occupation-imbalance exhaustion fade.

S350 anchors fair value to baseline typical price weighted by tick volume.
When recent closes spend an unusually large fraction of time on one side of
that anchor at a material distance, a swept rejection candle moving back
toward fair value is treated as an exhaustion reversal.

All occupation inputs precede the rejection candle.  Entry is next-open
market, SL is beyond the closed sweep extreme plus ATR, and TP is at least 7R.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 48,
    "RECENT_BARS": 20,
    "OCCUPATION_RATE_MIN": 0.75,
    "MEDIAN_DISTANCE_ATR_MIN": 0.65,
    "SWEEP_ATR_MIN": 0.02,
    "TOWARD_ANCHOR_ATR_MIN": 0.35,
    "REJECTION_BODY_ATR_MIN": 0.45,
    "REJECTION_RANGE_ATR_MIN": 0.80,
    "REJECTION_WICK_FRACTION_MIN": 0.18,
    "REJECTION_CLOSE_FRACTION": 0.70,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 8.0,
    "BE_RR": 0.08,
    "CANCEL_BARS": 3,
}


def _volume_weighted_anchor(bars):
    weighted_sum = 0.0
    volume_sum = 0.0
    for bar in bars:
        volume = float(bar.get("tick_volume", 0.0))
        typical = (
            float(bar["high"])
            + float(bar["low"])
            + float(bar["close"])
        ) / 3.0
        if not math.isfinite(volume) or not math.isfinite(typical):
            return None
        if volume <= 0.0:
            continue
        weighted_sum += typical * volume
        volume_sum += volume
    if volume_sum <= 0.0:
        return None
    return weighted_sum / volume_sum


def detect_s350(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade one-sided price occupation after a swept rejection."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        occupation_min = float(c["OCCUPATION_RATE_MIN"])
        distance_min = float(c["MEDIAN_DISTANCE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not (
        math.isfinite(occupation_min)
        and 0.5 <= occupation_min <= 1.0
        and math.isfinite(distance_min)
        and distance_min >= 0.0
    ):
        return _wait("Invalid config: occupation gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        anchor = _volume_weighted_anchor(baseline)
        atr = _atr(bars[:-1], period)
        recent_median = statistics.median(
            bar["close"] for bar in recent
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        ZeroDivisionError,
        AttributeError,
        statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    if anchor is None:
        return _wait("Volume-weighted anchor is unavailable")

    excursion_side = 1 if recent_median > anchor else -1
    occupation_rate = sum(
        (bar["close"] - anchor) * excursion_side > 0.0
        for bar in recent
    ) / len(recent)
    median_distance_atr = (
        excursion_side * (recent_median - anchor) / atr
    )
    if (
        occupation_rate < occupation_min
        or median_distance_atr < distance_min
    ):
        return _wait(
            f"No one-sided occupation imbalance "
            f"(rate={occupation_rate:.3f}, "
            f"median_distance={median_distance_atr:.3f}ATR)"
        )

    recent_edge = (
        max(bar["high"] for bar in recent)
        if excursion_side > 0
        else min(bar["low"] for bar in recent)
    )
    swept_price = (
        event["high"] if excursion_side > 0 else event["low"]
    )
    sweep_atr = excursion_side * (swept_price - recent_edge) / atr
    if sweep_atr < float(c["SWEEP_ATR_MIN"]):
        return _wait("Rejection candle did not sweep recent occupation edge")

    side = -excursion_side
    toward_anchor = side * (
        event["close"] - recent[-1]["close"]
    ) / atr
    if toward_anchor < float(c["TOWARD_ANCHOR_ATR_MIN"]):
        return _wait("Rejection did not move materially toward fair value")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Rejection body does not confirm the fade")
    if abs(body) < atr * float(c["REJECTION_BODY_ATR_MIN"]):
        return _wait("Rejection body is too small versus ATR")
    if candle_range < atr * float(c["REJECTION_RANGE_ATR_MIN"]):
        return _wait("Rejection range is too small versus ATR")
    rejection_wick = (
        event["high"] - max(event["open"], event["close"])
        if side < 0
        else min(event["open"], event["close"]) - event["low"]
    )
    wick_fraction = rejection_wick / candle_range
    if wick_fraction < float(c["REJECTION_WICK_FRACTION_MIN"]):
        return _wait("Rejection wick is too small")
    close_fraction = (
        (event["close"] - event["low"]) / candle_range
        if side > 0
        else (event["high"] - event["close"]) / candle_range
    )
    if close_fraction < float(c["REJECTION_CLOSE_FRACTION"]):
        return _wait("Rejection lacks directional close control")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(event["close"], 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor(
            (event["low"] - sl_buffer + 1e-12) * 100.0
        ) / 100.0
    else:
        sl = math.ceil(
            (event["high"] + sl_buffer - 1e-12) * 100.0
        ) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Rejection risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Rejection risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    tp = (
        math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
        if side > 0
        else math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    )
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S350 {signal} Occupation Exhaustion {rr:g}R",
        "reason": (
            f"VW anchor={anchor:.2f}, occupation={occupation_rate:.3f}, "
            f"distance={median_distance_atr:.3f}ATR, "
            f"sweep={sweep_atr:.3f}ATR, wick={wick_fraction:.3f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
