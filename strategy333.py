# -*- coding: utf-8 -*-
"""S333 - Lagged directional participation-response release.

S333 asks whether a positive or negative closed return is followed by an
unusually high-volume bar more often than the unconditional rate.  Smoothed
log-odds measure that one-bar lagged response separately for each direction.
A recent increase and directional asymmetry indicate order-flow participation
following one side of price discovery rather than contemporaneous volatility.

All response samples precede the release candle.  Entry is simulated at the
next open, the stop is beyond the closed release extreme plus ATR, and the
target is at least 7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_PAIRS": 68,
    "RECENT_PAIRS": 24,
    "VOLUME_STATE_QUANTILE": 0.65,
    "LAPLACE_ALPHA": 1.0,
    "MIN_SIDE_OBSERVATIONS": 5,
    "RECENT_RESPONSE_MIN": 0.22,
    "RESPONSE_JUMP_MIN": 0.14,
    "RESPONSE_ASYMMETRY_MIN": 0.575,
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
    "TP_RR": 9.0,
    "BE_RR": 0.06,
    "CANCEL_BARS": 3,
}


def _quantile(values, probability):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _logit(probability):
    return math.log(probability / (1.0 - probability))


def _participation_response(bars, probability, alpha, minimum_observations):
    """Return BUY/SELL next-volume response log-odds without future leakage."""
    if len(bars) < minimum_observations * 2 + 2:
        return None
    target_volumes = [float(bar["tick_volume"]) for bar in bars[2:]]
    if any(not math.isfinite(value) or value < 0.0 for value in target_volumes):
        return None
    threshold = _quantile(target_volumes, probability)
    if threshold is None:
        return None

    observations = {1: 0, -1: 0}
    high_counts = {1: 0, -1: 0}
    total_high = 0
    total = 0
    for index in range(1, len(bars) - 1):
        previous = float(bars[index - 1]["close"])
        current = float(bars[index]["close"])
        if (
            not math.isfinite(previous)
            or not math.isfinite(current)
            or previous <= 0.0
            or current <= 0.0
        ):
            return None
        signed_return = math.log(current / previous)
        if signed_return == 0.0:
            continue
        side = 1 if signed_return > 0.0 else -1
        high_state = float(bars[index + 1]["tick_volume"]) >= threshold
        observations[side] += 1
        high_counts[side] += int(high_state)
        total += 1
        total_high += int(high_state)

    if (
        total < minimum_observations * 2
        or min(observations.values()) < minimum_observations
    ):
        return None
    unconditional = (total_high + alpha) / (total + 2.0 * alpha)
    base_log_odds = _logit(unconditional)
    responses = {}
    for side in (1, -1):
        conditional = (
            high_counts[side] + alpha
        ) / (observations[side] + 2.0 * alpha)
        responses[side] = _logit(conditional) - base_log_odds
    return responses[1], responses[-1], observations[1], observations[-1]


def detect_s333(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after one direction gains lagged volume response."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_pairs = max(16, int(c["BASELINE_PAIRS"]))
        recent_pairs = max(12, int(c["RECENT_PAIRS"]))
        probability = float(c["VOLUME_STATE_QUANTILE"])
        alpha = float(c["LAPLACE_ALPHA"])
        minimum_observations = max(2, int(c["MIN_SIDE_OBSERVATIONS"]))
        recent_min = float(c["RECENT_RESPONSE_MIN"])
        jump_min = float(c["RESPONSE_JUMP_MIN"])
        asymmetry_min = float(c["RESPONSE_ASYMMETRY_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if (
        not 0.50 <= probability <= 0.90
        or not math.isfinite(alpha)
        or alpha <= 0.0
        or not all(
            math.isfinite(value) and value >= 0.0
            for value in (recent_min, jump_min, asymmetry_min)
        )
    ):
        return _wait("Invalid config: participation-response gates are invalid")

    required = max(period + 5, baseline_pairs + recent_pairs + 4)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_pairs - recent_pairs - 3:-1]
        baseline = history[:baseline_pairs + 2]
        recent = history[baseline_pairs:]
        baseline_response = _participation_response(
            baseline, probability, alpha, minimum_observations
        )
        recent_response = _participation_response(
            recent, probability, alpha, minimum_observations
        )
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
    if baseline_response is None or recent_response is None:
        return _wait("Lagged participation response is unavailable")

    baseline_buy, baseline_sell, _, _ = baseline_response
    recent_buy, recent_sell, recent_buy_n, recent_sell_n = recent_response
    side = 1 if recent_buy > recent_sell else -1
    recent_side = recent_buy if side > 0 else recent_sell
    recent_other = recent_sell if side > 0 else recent_buy
    baseline_side = baseline_buy if side > 0 else baseline_sell
    response_jump = recent_side - baseline_side
    asymmetry = recent_side - recent_other
    if (
        recent_side < recent_min
        or response_jump < jump_min
        or asymmetry < asymmetry_min
    ):
        return _wait(
            f"No lagged participation shift ({recent_side:.3f}, "
            f"jump={response_jump:.3f}, asym={asymmetry:.3f})"
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
        return _wait("Recent path opposes participation-response direction")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes participation-response direction")
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
        "pattern": f"S333 {signal} Lagged Participation {rr:g}R",
        "reason": (
            f"response {baseline_side:.4f}->{recent_side:.4f}, "
            f"jump={response_jump:.4f}, asymmetry={asymmetry:.4f}, "
            f"recent_n={recent_buy_n}/{recent_sell_n}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
