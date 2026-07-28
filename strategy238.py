# -*- coding: utf-8 -*-
"""S238 - Signed-effort absorption release breakout, 10R.

Tick volume is weighted by each bar's signed body-to-range efficiency.  Strong
cumulative effort with little net price displacement suggests passive
absorption; an efficient break in the effort direction is treated as release
of the accumulated imbalance.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "EFFORT_WINDOW": 24,
    "EFFORT_MODE": "body",
    "BREAK_RANGE_BARS": 8,
    "MIN_SIGNED_EFFORT": 0.18,
    "MAX_PRICE_DISPLACEMENT_ATR": 0.60,
    "BREAK_BODY_MIN_FRACTION": 0.55,
    "BREAK_BODY_MIN_ATR": 0.30,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s238(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade release of absorbed signed tick-volume effort."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        effort_window = max(8, int(c["EFFORT_WINDOW"]))
        range_bars = max(4, int(c["BREAK_RANGE_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
        effort_mode = str(c["EFFORT_MODE"]).strip().lower()
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if effort_mode not in ("body", "clv"):
        return _wait(f"Invalid effort mode: {effort_mode}")
    required = max(period + 5, effort_window + 3, range_bars + 3)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    history = bars[-effort_window - 1:-1]
    signed_effort = 0.0
    total_volume = 0.0
    for bar in history:
        bar_range = float(bar["high"]) - float(bar["low"])
        volume = max(0.0, float(bar.get("tick_volume", 0.0)))
        if bar_range > 0.0 and volume > 0.0:
            if effort_mode == "clv":
                signed_unit = (
                    (float(bar["close"]) - float(bar["low"]))
                    - (float(bar["high"]) - float(bar["close"]))
                ) / bar_range
            else:
                signed_unit = (
                    float(bar["close"]) - float(bar["open"])
                ) / bar_range
            signed_effort += volume * signed_unit
            total_volume += volume
    if total_volume <= 0.0:
        return _wait("Tick volume is unavailable")
    effort_ratio = signed_effort / total_volume
    if abs(effort_ratio) < float(c["MIN_SIGNED_EFFORT"]):
        return _wait(f"Signed effort is weak ({effort_ratio:.2f})")
    displacement = (
        float(history[-1]["close"]) - float(history[0]["open"])
    ) / atr
    if abs(displacement) > float(c["MAX_PRICE_DISPLACEMENT_ATR"]):
        return _wait(f"Price already displaced ({displacement:.2f} ATR)")

    structure = bars[-range_bars - 1:-1]
    range_high = max(float(bar["high"]) for bar in structure)
    range_low = min(float(bar["low"]) for bar in structure)
    breakout = bars[-1]
    body = float(breakout["close"]) - float(breakout["open"])
    bar_range = float(breakout["high"]) - float(breakout["low"])
    if effort_ratio > 0.0 and breakout["close"] > range_high and body > 0.0:
        side = 1
    elif effort_ratio < 0.0 and breakout["close"] < range_low and body < 0.0:
        side = -1
    else:
        return _wait("No range release in the signed-effort direction")
    if bar_range <= 0.0:
        return _wait("Breakout bar range is zero")
    if abs(body) < bar_range * float(c["BREAK_BODY_MIN_FRACTION"]):
        return _wait("Release bar lacks directional efficiency")
    if abs(body) < atr * float(c["BREAK_BODY_MIN_ATR"]):
        return _wait("Release body is too small versus ATR")

    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(float(breakout["close"]), 2)
    if side > 0:
        sl = math.floor(
            (float(breakout["low"]) - buffer + 1e-12) * 100.0
        ) / 100.0
    else:
        sl = math.ceil(
            (float(breakout["high"]) + buffer - 1e-12) * 100.0
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
    if side > 0:
        signal = "BUY"
        tp = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
    else:
        signal = "SELL"
        tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S238 {signal} Signed-Effort Release {rr:g}R",
        "reason": (
            f"Efficient release after absorbed signed effort "
            f"(effort={effort_ratio:.2f}, displacement={displacement:.2f} ATR)"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
