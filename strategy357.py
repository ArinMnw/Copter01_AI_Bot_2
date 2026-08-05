# -*- coding: utf-8 -*-
"""S357 - Directional displacement-concentration release.

S357 measures how much of a closed path's favorable displacement is carried by
its largest directional return bars.  A rising top-k concentration versus
disjoint baseline blocks indicates that a small number of institutional-sized
impulses dominate price discovery rather than diffuse random drift.

All concentration and path inputs precede the release candle.  Entry is
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
    "BASELINE_BARS": 80,
    "RECENT_BARS": 20,
    "TOP_RETURNS": 3,
    "CONCENTRATION_MIN": 0.52,
    "CONCENTRATION_JUMP_MIN": 0.10,
    "ADVERSE_SHARE_MAX": 0.42,
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
    "BE_RR": 0.08,
    "CANCEL_BARS": 3,
}


def _concentration_profile(bars, top_returns):
    if len(bars) < 8:
        return None
    closes = [float(bar["close"]) for bar in bars]
    if not all(math.isfinite(value) for value in closes):
        return None
    returns = [
        closes[index] - closes[index - 1]
        for index in range(1, len(closes))
    ]
    net_move = closes[-1] - closes[0]
    if abs(net_move) <= 1e-12:
        return None
    side = 1 if net_move > 0.0 else -1
    favorable = [max(0.0, side * value) for value in returns]
    adverse = [max(0.0, -side * value) for value in returns]
    favorable_total = sum(favorable)
    adverse_total = sum(adverse)
    travelled = favorable_total + adverse_total
    if favorable_total <= 0.0 or travelled <= 0.0:
        return None
    count = min(max(1, top_returns), len(favorable))
    concentration = sum(sorted(favorable, reverse=True)[:count]) / favorable_total
    adverse_share = adverse_total / travelled
    efficiency = abs(net_move) / travelled
    return (
        concentration,
        adverse_share,
        side,
        net_move,
        efficiency,
    )


def detect_s357(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after favorable displacement becomes concentrated."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        top_returns = max(1, int(c["TOP_RETURNS"]))
        concentration_min = float(c["CONCENTRATION_MIN"])
        concentration_jump_min = float(c["CONCENTRATION_JUMP_MIN"])
        adverse_share_max = float(c["ADVERSE_SHARE_MAX"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (
            concentration_min,
            concentration_jump_min,
            adverse_share_max,
        )
    ):
        return _wait("Invalid config: displacement gates are invalid")

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
        baseline_concentrations = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _concentration_profile(
                baseline[start:start + recent_count],
                top_returns,
            )
            if profile is not None:
                baseline_concentrations.append(profile[0])
        recent_profile = _concentration_profile(recent, top_returns)
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
    if recent_profile is None or not baseline_concentrations:
        return _wait("Displacement concentration is unavailable")

    concentration, adverse_share, side, net_move, efficiency = recent_profile
    baseline_concentration = statistics.median(baseline_concentrations)
    concentration_jump = concentration - baseline_concentration
    if (
        concentration < concentration_min
        or concentration_jump < concentration_jump_min
    ):
        return _wait(
            f"No displacement concentration shift "
            f"({baseline_concentration:.3f}->{concentration:.3f}, "
            f"jump={concentration_jump:.3f})"
        )
    if adverse_share > adverse_share_max:
        return _wait(f"Adverse displacement is excessive ({adverse_share:.3f})")
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Concentrated path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Concentrated net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes concentrated displacement")
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
        "pattern": f"S357 {signal} Displacement Concentration {rr:g}R",
        "reason": (
            f"top-{top_returns} concentration "
            f"{baseline_concentration:.4f}->{concentration:.4f}, "
            f"jump={concentration_jump:.4f}, adverse={adverse_share:.4f}, "
            f"efficiency={efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
