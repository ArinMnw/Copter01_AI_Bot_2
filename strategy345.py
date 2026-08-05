# -*- coding: utf-8 -*-
"""S345 - Directional wick-rejection pressure release.

S345 aggregates normalized lower-minus-upper wick pressure.  A shift toward
one-sided rejection, supported by a majority of recent candles, is treated as
latent directional pressure before a closed release candle.

All pressure and path inputs precede the release candle.  Entry is next-open
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
    "RECENT_WICK_PRESSURE_MIN": 0.12,
    "WICK_PRESSURE_SHIFT_MIN": 0.10,
    "WICK_COHERENCE_MIN": 0.55,
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


def _wick_profile(bars):
    if len(bars) < 8:
        return None
    pressures = []
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
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        pressures.append((lower_wick - upper_wick) / candle_range)
    if len(pressures) < max(6, len(bars) // 2):
        return None
    mean_pressure = sum(pressures) / len(pressures)
    side = 1 if mean_pressure > 0.0 else -1
    coherence = sum(
        pressure * side > 0.0 for pressure in pressures
    ) / len(pressures)
    return mean_pressure, coherence


def detect_s345(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after recent wick-rejection pressure shifts."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        pressure_min = float(c["RECENT_WICK_PRESSURE_MIN"])
        pressure_shift_min = float(c["WICK_PRESSURE_SHIFT_MIN"])
        coherence_min = float(c["WICK_COHERENCE_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (pressure_min, pressure_shift_min, coherence_min)
    ):
        return _wait("Invalid config: wick-pressure gates are invalid")

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
        baseline_profile = _wick_profile(baseline)
        recent_profile = _wick_profile(recent)
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
        return _wait("Wick-pressure profile is unavailable")

    baseline_pressure, _ = baseline_profile
    recent_pressure, coherence = recent_profile
    side = 1 if recent_pressure > 0.0 else -1
    pressure_shift = side * (recent_pressure - baseline_pressure)
    if (
        abs(recent_pressure) < pressure_min
        or pressure_shift < pressure_shift_min
        or coherence < coherence_min
    ):
        return _wait(
            f"No directional wick-pressure shift "
            f"({baseline_pressure:.3f}->{recent_pressure:.3f}, "
            f"shift={pressure_shift:.3f}, coherence={coherence:.3f})"
        )

    net_move = recent[-1]["close"] - recent[0]["close"]
    travelled = sum(
        abs(recent[index]["close"] - recent[index - 1]["close"])
        for index in range(1, len(recent))
    )
    if travelled <= 0.0 or net_move * side <= 0.0:
        return _wait("Recent path opposes wick-pressure direction")
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes wick-pressure direction")
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
        "pattern": f"S345 {signal} Wick Pressure {rr:g}R",
        "reason": (
            f"wick pressure {baseline_pressure:.4f}->"
            f"{recent_pressure:.4f}, shift={pressure_shift:.4f}, "
            f"coherence={coherence:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
