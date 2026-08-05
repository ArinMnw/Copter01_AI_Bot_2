# -*- coding: utf-8 -*-
"""S393 — Realized-Semivariance Dominance Release 9R.

Recent close returns are decomposed into upside and downside realized
semivariance.  Directional imbalance must strengthen versus an older baseline.
Bipower jump gating was falsified during optimization and remains available as
an optional diagnostic only.  A closed release candle confirms continuation and defines
an event-extreme plus ATR stop; market fills are evaluated at the next open.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 80,
    "RECENT_BARS": 24,
    "SEMIVARIANCE_IMBALANCE_MIN": 0.25,
    "SEMIVARIANCE_RISE_MIN": 0.15,
    "JUMP_RATIO_MIN": 0.00,
    "PATH_EFFICIENCY_MIN": 0.15,
    "NET_MOVE_ATR_MIN": 0.35,
    "EVENT_VOLUME_RATIO_MIN": 1.05,
    "EVENT_BODY_ATR_MIN": 0.65,
    "EVENT_RANGE_ATR_MIN": 0.75,
    "EVENT_BODY_FRACTION_MIN": 0.72,
    "EVENT_CLOSE_FRACTION": 0.75,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.18,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 9.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _variance_profile(bars):
    returns = [
        bars[index]["close"] - bars[index - 1]["close"]
        for index in range(1, len(bars))
    ]
    if len(returns) < 3:
        return None
    upside = sum(value * value for value in returns if value > 0.0)
    downside = sum(value * value for value in returns if value < 0.0)
    realized = upside + downside
    if realized <= 0.0:
        return None
    imbalance = (upside - downside) / realized
    bipower = math.pi / 2.0 * sum(
        abs(current) * abs(previous)
        for previous, current in zip(returns[:-1], returns[1:])
    )
    jump_ratio = max(0.0, (realized - bipower) / realized)
    travelled = sum(abs(value) for value in returns)
    return imbalance, jump_ratio, travelled


def detect_s393(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S393 payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(10, int(c["RECENT_BARS"]))
        imbalance_min = float(c["SEMIVARIANCE_IMBALANCE_MIN"])
        rise_min = float(c["SEMIVARIANCE_RISE_MIN"])
        jump_min = float(c["JUMP_RATIO_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_move_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (imbalance_min, rise_min, jump_min, path_min, net_move_min)
    ):
        return _wait("Invalid config: semivariance gates are invalid")
    required = max(period + 3, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates[-required:])
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        baseline_profile = _variance_profile(baseline)
        recent_profile = _variance_profile(recent)
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
    if baseline_profile is None or recent_profile is None or atr <= 0.0:
        return _wait("Semivariance profile or ATR is unavailable")
    baseline_imbalance, _, _ = baseline_profile
    recent_imbalance, jump_ratio, travelled = recent_profile
    if travelled <= 0.0:
        return _wait("Recent path is zero")
    if abs(recent_imbalance) < imbalance_min:
        return _wait(f"Semivariance imbalance is weak ({recent_imbalance:.3f})")
    side = 1 if recent_imbalance > 0.0 else -1
    imbalance_rise = side * (recent_imbalance - baseline_imbalance)
    if imbalance_rise < rise_min:
        return _wait(f"Directional semivariance has not risen ({imbalance_rise:.3f})")
    if jump_ratio < jump_min:
        return _wait(f"Discontinuous variance is weak ({jump_ratio:.3f})")
    net_move = recent[-1]["close"] - recent[0]["close"]
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Auction path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min or side * net_move <= 0.0:
        return _wait("Net move does not confirm semivariance direction")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or side * body <= 0.0:
        return _wait("Event does not confirm semivariance direction")
    median_volume = statistics.median(
        float(bar["tick_volume"]) for bar in recent
    )
    volume_ratio = event["tick_volume"] / median_volume
    if volume_ratio < float(c["EVENT_VOLUME_RATIO_MIN"]):
        return _wait(f"Event participation is weak ({volume_ratio:.3f}x)")
    if abs(body) < atr * float(c["EVENT_BODY_ATR_MIN"]):
        return _wait("Event body is too small versus ATR")
    if candle_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Event range is too small versus ATR")
    if abs(body) / candle_range < float(c["EVENT_BODY_FRACTION_MIN"]):
        return _wait("Event release lacks body control")
    location = (
        (event["close"] - event["low"]) / candle_range
        if side > 0
        else (event["high"] - event["close"]) / candle_range
    )
    if location < float(c["EVENT_CLOSE_FRACTION"]):
        return _wait(f"Event close lacks directional control ({location:.3f})")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(event["close"], 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor((event["low"] - sl_buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + sl_buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Event risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Event risk too large versus price")
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
        "pattern": f"S393 {signal} Realized-Semivariance Dominance {rr:g}R",
        "reason": (
            f"semivar={recent_imbalance:.4f}, baseline={baseline_imbalance:.4f}, "
            f"rise={imbalance_rise:.4f}, jump={jump_ratio:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
