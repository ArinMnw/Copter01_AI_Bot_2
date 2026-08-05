# -*- coding: utf-8 -*-
"""S359 - Bipower jump-variation directional release.

S359 separates discontinuous return energy from continuous volatility with a
realized-variance versus bipower-variation estimator.  It seeks a recent rise
in jump share versus disjoint baseline blocks, while squared-return energy,
net path, and a closed release all agree on direction.

All jump-variation and path inputs precede the release candle.  Entry is
next-open market, SL is beyond the closed release extreme plus ATR, and TP is
at least 7R.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 100,
    "RECENT_BARS": 20,
    "JUMP_SHARE_MIN": 0.18,
    "JUMP_SHARE_INCREASE_MIN": 0.16,
    "DIRECTIONAL_ENERGY_MIN": 0.24,
    "PATH_EFFICIENCY_MIN": 0.20,
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
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _jump_profile(bars):
    if len(bars) < 8:
        return None
    closes = [float(bar["close"]) for bar in bars]
    if not all(math.isfinite(value) for value in closes):
        return None
    returns = [
        closes[index] - closes[index - 1]
        for index in range(1, len(closes))
    ]
    realized_variance = sum(value * value for value in returns)
    if realized_variance <= 1e-18:
        return None
    bipower_variation = (
        math.pi
        / 2.0
        * sum(
            abs(returns[index]) * abs(returns[index - 1])
            for index in range(1, len(returns))
        )
    )
    jump_share = max(
        0.0,
        min(1.0, (realized_variance - bipower_variation) / realized_variance),
    )
    signed_energy = sum(
        math.copysign(value * value, value)
        for value in returns
        if value != 0.0
    ) / realized_variance
    net_move = closes[-1] - closes[0]
    if abs(net_move) <= 1e-12 or abs(signed_energy) <= 1e-12:
        return None
    side = 1 if net_move > 0.0 else -1
    if signed_energy * side <= 0.0:
        return None
    travelled = sum(abs(value) for value in returns)
    if travelled <= 0.0:
        return None
    efficiency = abs(net_move) / travelled
    return (
        jump_share,
        abs(signed_energy),
        side,
        net_move,
        efficiency,
    )


def detect_s359(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a directional release after estimated jump variation rises."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        jump_share_min = float(c["JUMP_SHARE_MIN"])
        jump_increase_min = float(c["JUMP_SHARE_INCREASE_MIN"])
        directional_energy_min = float(c["DIRECTIONAL_ENERGY_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (
            jump_share_min,
            jump_increase_min,
            directional_energy_min,
        )
    ):
        return _wait("Invalid config: jump-variation gates are invalid")

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
        baseline_jump_shares = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _jump_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_jump_shares.append(profile[0])
        recent_profile = _jump_profile(recent)
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
    if recent_profile is None or not baseline_jump_shares:
        return _wait("Jump-variation profile is unavailable")

    jump_share, directional_energy, side, net_move, efficiency = recent_profile
    baseline_jump_share = statistics.median(baseline_jump_shares)
    jump_increase = jump_share - baseline_jump_share
    if (
        jump_share < jump_share_min
        or jump_increase < jump_increase_min
    ):
        return _wait(
            f"No jump-variation expansion "
            f"({baseline_jump_share:.3f}->{jump_share:.3f}, "
            f"increase={jump_increase:.3f})"
        )
    if directional_energy < directional_energy_min:
        return _wait(
            f"Jump energy lacks direction ({directional_energy:.3f})"
        )
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Jump path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Jump path net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes jump-energy direction")
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
        "pattern": f"S359 {signal} Bipower Jump {rr:g}R",
        "reason": (
            f"jump share {baseline_jump_share:.4f}->{jump_share:.4f}, "
            f"increase={jump_increase:.4f}, "
            f"directional energy={directional_energy:.4f}, "
            f"efficiency={efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
