# -*- coding: utf-8 -*-
"""S351 - Price-bridge late-acceleration release.

S351 normalizes each close path to start at zero and end at one, then measures
its mean deviation from the straight endpoint chord.  A path that remains
behind the chord before catching up has negative bridge area and therefore
late directional acceleration.

All bridge and path inputs precede the release candle.  Entry is next-open
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
    "BASELINE_BARS": 80,
    "RECENT_BARS": 20,
    "RECENT_ACCELERATION_MIN": 0.10,
    "ACCELERATION_JUMP_MIN": 0.06,
    "TAIL_PROGRESS_MIN": 0.30,
    "TAIL_BARS": 5,
    "PATH_EFFICIENCY_MIN": 0.26,
    "NET_MOVE_ATR_MIN": 0.55,
    "RELEASE_BODY_ATR_MIN": 0.80,
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
    "TP_RR": 9.0,
    "BE_RR": 0.05,
    "CANCEL_BARS": 3,
}


def _bridge_profile(bars):
    if len(bars) < 8:
        return None
    closes = [float(bar["close"]) for bar in bars]
    if not all(math.isfinite(value) for value in closes):
        return None
    net_move = closes[-1] - closes[0]
    if abs(net_move) <= 1e-12:
        return None
    side = 1 if net_move > 0.0 else -1
    scale = abs(net_move)
    deviations = []
    denominator = len(closes) - 1
    for index, close in enumerate(closes):
        progress = side * (close - closes[0]) / scale
        chord = index / denominator
        deviations.append(progress - chord)
    bridge_area = sum(deviations[1:-1]) / max(1, len(deviations) - 2)
    travelled = sum(
        abs(closes[index] - closes[index - 1])
        for index in range(1, len(closes))
    )
    if travelled <= 0.0:
        return None
    efficiency = abs(net_move) / travelled
    return -bridge_area, side, net_move, efficiency


def detect_s351(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after price-path acceleration exceeds baseline."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        acceleration_min = float(c["RECENT_ACCELERATION_MIN"])
        acceleration_jump_min = float(c["ACCELERATION_JUMP_MIN"])
        tail_progress_min = float(c["TAIL_PROGRESS_MIN"])
        tail_bars = max(2, int(c["TAIL_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (
            acceleration_min,
            acceleration_jump_min,
            tail_progress_min,
        )
    ):
        return _wait("Invalid config: bridge-acceleration gates invalid")

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
        block_accelerations = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _bridge_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                block_accelerations.append(profile[0])
        recent_profile = _bridge_profile(recent)
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
    if recent_profile is None or not block_accelerations:
        return _wait("Price-bridge profile is unavailable")

    recent_acceleration, side, net_move, efficiency = recent_profile
    baseline_acceleration = statistics.median(block_accelerations)
    acceleration_jump = recent_acceleration - baseline_acceleration
    if (
        recent_acceleration < acceleration_min
        or acceleration_jump < acceleration_jump_min
    ):
        return _wait(
            f"No late price-bridge acceleration "
            f"({baseline_acceleration:.3f}->{recent_acceleration:.3f}, "
            f"jump={acceleration_jump:.3f})"
        )
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Accelerating path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Accelerating net move is too small")
    if tail_bars >= len(recent):
        return _wait("Invalid config: tail window too long")
    tail_move = recent[-1]["close"] - recent[-tail_bars - 1]["close"]
    tail_progress = side * tail_move / abs(net_move)
    if tail_progress < tail_progress_min:
        return _wait(
            f"Late path contributes too little ({tail_progress:.3f})"
        )

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes accelerating path")
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
        "pattern": f"S351 {signal} Bridge Acceleration {rr:g}R",
        "reason": (
            f"bridge acceleration {baseline_acceleration:.4f}->"
            f"{recent_acceleration:.4f}, jump={acceleration_jump:.4f}, "
            f"tail={tail_progress:.4f}, efficiency={efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
