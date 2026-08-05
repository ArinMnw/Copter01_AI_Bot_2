# -*- coding: utf-8 -*-
"""S352 - Price-bridge early-displacement exhaustion fade.

S352 is the falsification complement of S351.  It selects paths that move
ahead of their endpoint chord early and then decelerate, followed by a closed
rejection candle in the opposite direction.

All bridge and path inputs precede the rejection candle.  Entry is next-open
market, SL is beyond the closed rejection extreme plus ATR, and TP is at least
7R.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy351 import _bridge_profile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 80,
    "RECENT_BARS": 20,
    "RECENT_DECELERATION_MIN": 0.10,
    "DECELERATION_JUMP_MIN": 0.06,
    "EARLY_PROGRESS_MIN": 0.45,
    "EARLY_BARS": 5,
    "PATH_EFFICIENCY_MIN": 0.22,
    "NET_MOVE_ATR_MIN": 0.55,
    "REJECTION_BODY_ATR_MIN": 0.50,
    "REJECTION_RANGE_ATR_MIN": 0.80,
    "REJECTION_WICK_FRACTION_MIN": 0.15,
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


def detect_s352(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a path that displaced early and then decelerated."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        deceleration_min = float(c["RECENT_DECELERATION_MIN"])
        deceleration_jump_min = float(c["DECELERATION_JUMP_MIN"])
        early_progress_min = float(c["EARLY_PROGRESS_MIN"])
        early_bars = max(2, int(c["EARLY_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (
            deceleration_min,
            deceleration_jump_min,
            early_progress_min,
        )
    ):
        return _wait("Invalid config: bridge-deceleration gates invalid")

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
        block_decelerations = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _bridge_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                block_decelerations.append(-profile[0])
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
    if recent_profile is None or not block_decelerations:
        return _wait("Price-bridge profile is unavailable")

    recent_deceleration = -recent_profile[0]
    move_side = recent_profile[1]
    net_move = recent_profile[2]
    efficiency = recent_profile[3]
    baseline_deceleration = statistics.median(block_decelerations)
    deceleration_jump = recent_deceleration - baseline_deceleration
    if (
        recent_deceleration < deceleration_min
        or deceleration_jump < deceleration_jump_min
    ):
        return _wait(
            f"No early price-bridge deceleration "
            f"({baseline_deceleration:.3f}->{recent_deceleration:.3f}, "
            f"jump={deceleration_jump:.3f})"
        )
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Decelerating path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Decelerating net move is too small")
    if early_bars >= len(recent):
        return _wait("Invalid config: early window too long")
    early_move = (
        recent[early_bars]["close"] - recent[0]["close"]
    )
    early_progress = move_side * early_move / abs(net_move)
    if early_progress < early_progress_min:
        return _wait(
            f"Early path contributes too little ({early_progress:.3f})"
        )

    side = -move_side
    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Rejection body does not confirm exhaustion fade")
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
        "pattern": f"S352 {signal} Bridge Deceleration {rr:g}R",
        "reason": (
            f"bridge deceleration {baseline_deceleration:.4f}->"
            f"{recent_deceleration:.4f}, jump={deceleration_jump:.4f}, "
            f"early={early_progress:.4f}, wick={wick_fraction:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
