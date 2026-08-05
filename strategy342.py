# -*- coding: utf-8 -*-
"""S342 - Mann-Whitney volume-dominance release.

S342 estimates the probability that tick volume on positive-return bars
exceeds tick volume on negative-return bars.  The distribution-free AUC is
mapped to a signed dominance score, so it uses the full conditional volume
distributions rather than only tails or aggregate signed volume.

All dominance and path inputs precede the release candle.  Entry is next-open
market, SL is beyond the closed release extreme plus ATR, and TP is at least
7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 64,
    "RECENT_RETURNS": 24,
    "MIN_SIDE_OBSERVATIONS": 5,
    "RECENT_VOLUME_DOMINANCE_MIN": 0.25,
    "VOLUME_DOMINANCE_JUMP_MIN": 0.15,
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


def _volume_dominance(bars, minimum_observations):
    positive_volumes = []
    negative_volumes = []
    for index in range(1, len(bars)):
        previous = float(bars[index - 1]["close"])
        current = float(bars[index]["close"])
        volume = float(bars[index]["tick_volume"])
        if (
            not math.isfinite(previous)
            or not math.isfinite(current)
            or not math.isfinite(volume)
            or previous <= 0.0
            or current <= 0.0
            or volume < 0.0
        ):
            return None
        if current > previous:
            positive_volumes.append(volume)
        elif current < previous:
            negative_volumes.append(volume)
    if (
        len(positive_volumes) < minimum_observations
        or len(negative_volumes) < minimum_observations
    ):
        return None

    wins = 0.0
    for positive in positive_volumes:
        for negative in negative_volumes:
            if positive > negative:
                wins += 1.0
            elif positive == negative:
                wins += 0.5
    pairs = len(positive_volumes) * len(negative_volumes)
    auc = wins / pairs
    return 2.0 * (auc - 0.5), len(positive_volumes), len(negative_volumes)


def detect_s342(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after one direction gains full-distribution volume."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_RETURNS"]))
        recent_count = max(12, int(c["RECENT_RETURNS"]))
        minimum_observations = max(2, int(c["MIN_SIDE_OBSERVATIONS"]))
        dominance_min = float(c["RECENT_VOLUME_DOMINANCE_MIN"])
        dominance_jump_min = float(c["VOLUME_DOMINANCE_JUMP_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (dominance_min, dominance_jump_min)
    ):
        return _wait("Invalid config: volume-dominance gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 3)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 2:-1]
        baseline = history[:baseline_count + 1]
        recent = history[baseline_count:]
        baseline_profile = _volume_dominance(
            baseline, minimum_observations
        )
        recent_profile = _volume_dominance(recent, minimum_observations)
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
        return _wait("Mann-Whitney volume dominance is unavailable")

    baseline_score, _, _ = baseline_profile
    recent_score, recent_positive_n, recent_negative_n = recent_profile
    if recent_score == 0.0:
        return _wait("Recent volume distributions have no direction")
    side = 1 if recent_score > 0.0 else -1
    recent_side = abs(recent_score)
    baseline_side = baseline_score * side
    dominance_jump = recent_side - baseline_side
    if (
        recent_side < dominance_min
        or dominance_jump < dominance_jump_min
    ):
        return _wait(
            f"No volume-dominance shift "
            f"({baseline_side:.3f}->{recent_side:.3f}, "
            f"jump={dominance_jump:.3f})"
        )

    net_move = recent[-1]["close"] - recent[0]["close"]
    travelled = sum(
        abs(recent[index]["close"] - recent[index - 1]["close"])
        for index in range(1, len(recent))
    )
    if travelled <= 0.0:
        return _wait("Recent path has no movement")
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move is too small")
    if net_move * side <= 0.0:
        return _wait("Recent path opposes volume-dominance direction")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes volume-dominance direction")
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
        "pattern": f"S342 {signal} MW Volume Dominance {rr:g}R",
        "reason": (
            f"volume dominance {baseline_side:.4f}->{recent_side:.4f}, "
            f"jump={dominance_jump:.4f}, "
            f"recent_n={recent_positive_n}/{recent_negative_n}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
