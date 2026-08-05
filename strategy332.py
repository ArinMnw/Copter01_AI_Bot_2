# -*- coding: utf-8 -*-
"""S332 - Directional return-volume tail-copula release.

For each sample, S332 estimates conditional co-exceedance between upper-tail
tick volume and either the upper or lower tail of signed closed returns.  A
rising, asymmetric recent tail dependence identifies participation attached
specifically to bullish or bearish price discovery rather than to volatility
in general.

Every copula input precedes the release candle.  Entry is next-open market, the
stop is beyond the release extreme plus ATR, and TP is at least 7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 64,
    "RECENT_RETURNS": 20,
    "TAIL_QUANTILE": 0.75,
    "RECENT_TAIL_DEP_MIN": 0.55,
    "TAIL_DEP_JUMP_MIN": 0.20,
    "TAIL_ASYMMETRY_MIN": 0.35,
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
    "TP_RR": 12.0,
    "BE_RR": 0.08,
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


def _return_volume_sample(bars):
    returns = []
    volumes = []
    for index in range(1, len(bars)):
        previous = float(bars[index - 1]["close"])
        current = float(bars[index]["close"])
        volume = float(bars[index]["tick_volume"])
        if previous <= 0.0 or current <= 0.0 or volume < 0.0:
            return None
        returns.append(math.log(current / previous))
        volumes.append(volume)
    return returns, volumes


def _tail_dependence(bars, probability):
    sample = _return_volume_sample(bars)
    if sample is None:
        return None
    returns, volumes = sample
    if len(returns) < 8:
        return None
    upper_return = _quantile(returns, probability)
    lower_return = _quantile(returns, 1.0 - probability)
    upper_volume = _quantile(volumes, probability)
    volume_tail = [
        index for index, value in enumerate(volumes)
        if value >= upper_volume
    ]
    if len(volume_tail) < 3:
        return None
    upper_joint = sum(
        returns[index] >= upper_return for index in volume_tail
    )
    lower_joint = sum(
        returns[index] <= lower_return for index in volume_tail
    )
    denominator = len(volume_tail)
    return upper_joint / denominator, lower_joint / denominator


def detect_s332(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after directional return-volume tail dependence rises."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_RETURNS"]))
        recent_count = max(8, int(c["RECENT_RETURNS"]))
        probability = float(c["TAIL_QUANTILE"])
        recent_min = float(c["RECENT_TAIL_DEP_MIN"])
        jump_min = float(c["TAIL_DEP_JUMP_MIN"])
        asymmetry_min = float(c["TAIL_ASYMMETRY_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if (
        not math.isfinite(probability)
        or not 0.50 <= probability <= 0.90
        or not all(
            math.isfinite(value) and value >= 0.0
            for value in (recent_min, jump_min, asymmetry_min)
        )
    ):
        return _wait("Invalid config: tail-copula gates are invalid")

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
        baseline_dep = _tail_dependence(baseline, probability)
        recent_dep = _tail_dependence(recent, probability)
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
    if baseline_dep is None or recent_dep is None:
        return _wait("Directional tail dependence is unavailable")
    upper_recent, lower_recent = recent_dep
    side = 1 if upper_recent > lower_recent else -1
    recent_side = upper_recent if side > 0 else lower_recent
    recent_other = lower_recent if side > 0 else upper_recent
    baseline_side = baseline_dep[0] if side > 0 else baseline_dep[1]
    dependence_jump = recent_side - baseline_side
    asymmetry = recent_side - recent_other
    if (
        recent_side < recent_min
        or dependence_jump < jump_min
        or asymmetry < asymmetry_min
    ):
        return _wait(
            f"No directional tail-copula shift ({recent_side:.3f}, "
            f"jump={dependence_jump:.3f}, asym={asymmetry:.3f})"
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
        return _wait("Recent path opposes tail-copula direction")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes tail-copula direction")
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
        "pattern": f"S332 {signal} Directional Tail Copula {rr:g}R",
        "reason": (
            f"tail dependence {baseline_side:.4f}->{recent_side:.4f}, "
            f"jump={dependence_jump:.4f}, asymmetry={asymmetry:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
