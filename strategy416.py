# -*- coding: utf-8 -*-
"""S416 — Bipower Jump-Energy Release 7R.

Realized variance reacts to both continuous movement and jumps, while bipower
variation is comparatively robust to isolated jumps.  S416 compares their
ratio in a recent closed-bar window with disjoint baseline blocks, then uses
signed quadratic-return energy to identify the side dominating jump risk.
Entry is next-open after a participated confirmation event, with a dynamic
event-extreme ATR stop and a target of at least 7R.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 24,
    "JUMP_RATIO_MIN": 0.90,
    "JUMP_EXPANSION_RATIO_MIN": 1.10,
    "JUMP_RISE_MIN": 0.05,
    "SIGNED_ENERGY_MIN": 0.08,
    "FADE_JUMP": False,
    "EVENT_VOLUME_RATIO_MIN": 1.00,
    "EVENT_BODY_ATR_MIN": 0.45,
    "EVENT_RANGE_ATR_MIN": 0.65,
    "EVENT_BODY_FRACTION_MIN": 0.60,
    "EVENT_CLOSE_FRACTION": 0.70,
    "SESSION_START_HOUR": 0,
    "SESSION_END_HOUR": 24,
    "SL_BUFFER_ATR": 0.18,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 7.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _jump_metrics(bars):
    returns = []
    for previous, current in zip(bars, bars[1:]):
        left = previous["close"]
        right = current["close"]
        if min(left, right) <= 0.0:
            return None
        returns.append(math.log(right / left))
    if len(returns) < 10:
        return None
    realized = sum(value * value for value in returns)
    bipower_terms = [
        abs(returns[index] * returns[index - 1])
        for index in range(1, len(returns))
    ]
    if realized <= 0.0 or not bipower_terms:
        return None
    bipower = (
        math.pi / 2.0
        * len(returns) / len(bipower_terms)
        * sum(bipower_terms)
    )
    if bipower <= 0.0:
        return None
    return {
        "jump_ratio": realized / bipower,
        "signed_energy": sum(value * abs(value) for value in returns) / realized,
    }


def detect_s416(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S416 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        jump_min = float(c["JUMP_RATIO_MIN"])
        expansion_min = float(c["JUMP_EXPANSION_RATIO_MIN"])
        rise_min = float(c["JUMP_RISE_MIN"])
        energy_min = float(c["SIGNED_ENERGY_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: jump windows are inconsistent")
    if not all(math.isfinite(value) and value >= 0.0
               for value in (jump_min, expansion_min, rise_min, energy_min)):
        return _wait("Invalid config: jump gates are invalid")
    if energy_min > 1.0 or not 0 <= start_hour < end_hour <= 24:
        return _wait("Invalid config: energy or session gate is out of range")
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
        segment_count = baseline_count // recent_count
        baseline = baseline[-segment_count * recent_count:]
        baseline_metrics = [
            _jump_metrics(baseline[index:index + recent_count])
            for index in range(0, len(baseline), recent_count)
        ]
        recent_metrics = _jump_metrics(recent)
        if recent_metrics is None or any(item is None for item in baseline_metrics):
            return _wait("Bipower jump metric is unavailable")
        baseline_jump = statistics.median(
            item["jump_ratio"] for item in baseline_metrics
        )
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if baseline_jump <= 0.0 or atr <= 0.0:
        return _wait("Jump baseline or ATR is unavailable")
    jump_ratio = recent_metrics["jump_ratio"]
    expansion = jump_ratio / baseline_jump
    rise = jump_ratio - baseline_jump
    if jump_ratio < jump_min:
        return _wait(f"Absolute jump ratio is weak ({jump_ratio:.3f})")
    if expansion < expansion_min:
        return _wait(f"Jump expansion is weak ({expansion:.3f})")
    if rise < rise_min:
        return _wait(f"Jump-ratio rise is weak ({rise:.3f})")
    signed_energy = recent_metrics["signed_energy"]
    if abs(signed_energy) < energy_min:
        return _wait(f"Signed jump energy is weak ({signed_energy:.3f})")
    jump_side = 1 if signed_energy > 0.0 else -1
    trade_side = -jump_side if bool(c["FADE_JUMP"]) else jump_side

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or trade_side * body <= 0.0:
        return _wait("Event direction does not confirm jump-energy setup")
    median_volume = statistics.median(float(bar["tick_volume"]) for bar in recent)
    if median_volume <= 0.0:
        return _wait("Recent volume is unavailable")
    volume_ratio = event["tick_volume"] / median_volume
    if volume_ratio < float(c["EVENT_VOLUME_RATIO_MIN"]):
        return _wait(f"Event participation is weak ({volume_ratio:.3f}x)")
    if abs(body) < atr * float(c["EVENT_BODY_ATR_MIN"]):
        return _wait("Event body is too small versus ATR")
    if candle_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Event range is too small versus ATR")
    if abs(body) / candle_range < float(c["EVENT_BODY_FRACTION_MIN"]):
        return _wait("Event lacks directional body control")
    location = ((event["close"] - event["low"]) / candle_range
                if trade_side > 0 else
                (event["high"] - event["close"]) / candle_range)
    if location < float(c["EVENT_CLOSE_FRACTION"]):
        return _wait(f"Event close lacks directional control ({location:.3f})")

    signal = "BUY" if trade_side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(event["close"], 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if trade_side > 0:
        sl = math.floor((event["low"] - sl_buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + sl_buffer - 1e-12) * 100.0) / 100.0
    risk = trade_side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Event risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Event risk too large versus price")
    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + trade_side * rr * risk
    tp = (math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
          if trade_side > 0 else
          math.floor((raw_tp + 1e-12) * 100.0) / 100.0)
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S416 {signal} Bipower Jump-Energy {rr:g}R",
        "reason": (
            f"jump={jump_ratio:.4f}, baseline={baseline_jump:.4f}, "
            f"expansion={expansion:.4f}, rise={rise:.4f}, "
            f"signed_energy={signed_energy:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
