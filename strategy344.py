# -*- coding: utf-8 -*-
"""S344 - Circular candle-control synchronization release.

Each closed candle is mapped to a unit vector whose coordinates are its
signed body fraction and close-location value.  A rising mean-resultant length
means that candle control is becoming synchronized rather than cancelling out.

All profile and path inputs precede the release candle.  Entry is next-open
market, SL is beyond the closed release extreme plus ATR, and TP is at least
7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 64,
    "RECENT_BARS": 20,
    "RECENT_RESULTANT_MIN": 0.72,
    "RESULTANT_JUMP_MIN": 0.12,
    "DIRECTIONAL_COMPONENT_MIN": 0.55,
    "PATH_EFFICIENCY_MIN": 0.22,
    "NET_MOVE_ATR_MIN": 0.55,
    "RELEASE_BODY_ATR_MIN": 0.72,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.80,
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


def _control_profile(bars):
    """Return circular concentration and signed directional component."""
    if len(bars) < 8:
        return None
    vectors = []
    for bar in bars:
        high = float(bar["high"])
        low = float(bar["low"])
        open_price = float(bar["open"])
        close = float(bar["close"])
        if not all(
            math.isfinite(value)
            for value in (high, low, open_price, close)
        ):
            return None
        candle_range = high - low
        if candle_range <= 0.0:
            continue
        body_fraction = (close - open_price) / candle_range
        close_location = (2.0 * close - high - low) / candle_range
        magnitude = math.hypot(body_fraction, close_location)
        if magnitude <= 1e-12:
            continue
        vectors.append(
            (body_fraction / magnitude, close_location / magnitude)
        )
    if len(vectors) < max(6, len(bars) // 2):
        return None
    mean_x = sum(vector[0] for vector in vectors) / len(vectors)
    mean_y = sum(vector[1] for vector in vectors) / len(vectors)
    resultant = math.hypot(mean_x, mean_y)
    directional = (mean_x + mean_y) / math.sqrt(2.0)
    return resultant, directional


def detect_s344(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after candle-control vectors synchronize."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        recent_resultant_min = float(c["RECENT_RESULTANT_MIN"])
        resultant_jump_min = float(c["RESULTANT_JUMP_MIN"])
        directional_min = float(c["DIRECTIONAL_COMPONENT_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (
            recent_resultant_min,
            resultant_jump_min,
            directional_min,
        )
    ):
        return _wait("Invalid config: circular-control gates are invalid")

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
        baseline_profile = _control_profile(baseline)
        recent_profile = _control_profile(recent)
        atr = _atr(bars[:-1], period)
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
    if baseline_profile is None or recent_profile is None:
        return _wait("Circular candle-control profile is unavailable")

    baseline_resultant, _ = baseline_profile
    recent_resultant, directional = recent_profile
    resultant_jump = recent_resultant - baseline_resultant
    if (
        recent_resultant < recent_resultant_min
        or resultant_jump < resultant_jump_min
        or abs(directional) < directional_min
    ):
        return _wait(
            f"No candle-control synchronization "
            f"(R={baseline_resultant:.3f}->{recent_resultant:.3f}, "
            f"jump={resultant_jump:.3f}, direction={directional:.3f})"
        )

    side = 1 if directional > 0.0 else -1
    net_move = recent[-1]["close"] - recent[0]["close"]
    travelled = sum(
        abs(recent[index]["close"] - recent[index - 1]["close"])
        for index in range(1, len(recent))
    )
    if travelled <= 0.0 or net_move * side <= 0.0:
        return _wait("Recent path opposes circular-control direction")
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes synchronized candle control")
    if abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if candle_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    close_fraction = (
        (event["close"] - event["low"]) / candle_range
        if side > 0
        else (event["high"] - event["close"]) / candle_range
    )
    if close_fraction < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Release lacks directional close control")

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
        return _wait(f"Release risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Release risk too large versus price")

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
        "pattern": f"S344 {signal} Circular Control {rr:g}R",
        "reason": (
            f"control resultant {baseline_resultant:.4f}->"
            f"{recent_resultant:.4f}, jump={resultant_jump:.4f}, "
            f"direction={directional:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
