# -*- coding: utf-8 -*-
"""S353 - Haar-wavelet coarse-energy coherence release.

S353 applies an orthonormal Haar transform to closed returns.  The squared
final approximation coefficient divided by total return energy measures how
much activity is coherent directional drift rather than high-frequency detail.
Recent coherence must exceed both an absolute floor and baseline block median.

All wavelet and path inputs precede the release candle.  Entry is next-open
market, SL is beyond the closed release extreme plus ATR, and TP is at least
7R.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 96,
    "RECENT_RETURNS": 32,
    "RECENT_COHERENCE_MIN": 0.15,
    "COHERENCE_JUMP_MIN": 0.08,
    "PATH_EFFICIENCY_MIN": 0.24,
    "NET_MOVE_ATR_MIN": 0.70,
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


def _is_power_of_two(value):
    return value > 0 and value & (value - 1) == 0


def _haar_coherence(values):
    if len(values) < 8 or not _is_power_of_two(len(values)):
        return None
    if not all(math.isfinite(value) for value in values):
        return None
    total_energy = sum(value * value for value in values)
    if total_energy <= 1e-18:
        return None
    approximation = list(values)
    scale = math.sqrt(2.0)
    while len(approximation) > 1:
        approximation = [
            (approximation[index] + approximation[index + 1]) / scale
            for index in range(0, len(approximation), 2)
        ]
    coherence = approximation[0] * approximation[0] / total_energy
    direction = 1 if approximation[0] > 0.0 else -1
    return coherence, direction


def detect_s353(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after coarse Haar energy overtakes detail noise."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(32, int(c["BASELINE_RETURNS"]))
        recent_count = max(8, int(c["RECENT_RETURNS"]))
        coherence_min = float(c["RECENT_COHERENCE_MIN"])
        coherence_jump_min = float(c["COHERENCE_JUMP_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if (
        not _is_power_of_two(recent_count)
        or baseline_count < recent_count
        or baseline_count % recent_count != 0
    ):
        return _wait(
            "Invalid config: wavelet windows must be aligned powers of two"
        )
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (coherence_min, coherence_jump_min)
    ):
        return _wait("Invalid config: Haar coherence gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 2)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 2:-1]
        returns = [
            history[index]["close"] - history[index - 1]["close"]
            for index in range(1, len(history))
        ]
        baseline = returns[:baseline_count]
        recent = returns[baseline_count:]
        baseline_coherences = []
        for start in range(0, baseline_count, recent_count):
            profile = _haar_coherence(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_coherences.append(profile[0])
        recent_profile = _haar_coherence(recent)
        atr = _atr(bars[:-1], period)
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
    if recent_profile is None or not baseline_coherences:
        return _wait("Haar coherence profile is unavailable")

    recent_coherence, side = recent_profile
    baseline_coherence = statistics.median(baseline_coherences)
    coherence_jump = recent_coherence - baseline_coherence
    if (
        recent_coherence < coherence_min
        or coherence_jump < coherence_jump_min
    ):
        return _wait(
            f"No coarse Haar-energy shift "
            f"({baseline_coherence:.3f}->{recent_coherence:.3f}, "
            f"jump={coherence_jump:.3f})"
        )

    recent_bars = history[-recent_count - 1:]
    net_move = recent_bars[-1]["close"] - recent_bars[0]["close"]
    travelled = sum(
        abs(
            recent_bars[index]["close"]
            - recent_bars[index - 1]["close"]
        )
        for index in range(1, len(recent_bars))
    )
    if travelled <= 0.0 or net_move * side <= 0.0:
        return _wait("Recent path opposes Haar-energy direction")
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Coherent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Coherent net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes Haar-energy direction")
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
        "pattern": f"S353 {signal} Haar Coherence {rr:g}R",
        "reason": (
            f"Haar coherence {baseline_coherence:.4f}->"
            f"{recent_coherence:.4f}, jump={coherence_jump:.4f}, "
            f"efficiency={efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
