# -*- coding: utf-8 -*-
"""S220 - Afternoon breakout fade (13-19 BKK), 10R.

Motivation is empirical, not theoretical. The 24-hour session scan
(`scan_session_hours.py`) showed the drive skeleton losing money in EVERY
two-hour window between 13:00 and 19:00 BKK, in BOTH validation half-years:

    13-15: 2026 -342 / 2025 -16      16-18: 2026 -38  / 2025 -167
    14-16: 2026 -273 / 2025 -128     17-19: 2026 -100 / 2025 -7
    15-17: 2026 -337 / 2025 -45

That is a two-window-consistent statement that afternoon breakouts revert. S220
takes the same micro-range breakout S206 trades, and enters the OPPOSITE side.
Risk stays short because the stop sits just past the breakout bar's own wick
(which is close to the entry on a breakout close), so the payoff still clears
the project's RR>=7 bar.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy218 import _breakout_side


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 13,
    "SESSION_END_HOUR": 19,
    "RANGE_BARS": 8,
    "BREAK_BODY_MIN_FRACTION": 0.40,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s220(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade the micro-range breakout during the afternoon reversion window."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        range_bars = max(4, int(c["RANGE_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = range_bars + period + 6
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside afternoon reversion window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    micro_range = bars[-range_bars - 1:-1]
    breakout = bars[-1]
    detected = _breakout_side(micro_range, breakout,
                              float(c["BREAK_BODY_MIN_FRACTION"]))
    if detected is None:
        return _wait("No directional breakout to fade")
    drive_side, range_size = detected
    side = -drive_side  # the whole point: take the other side of the break

    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(breakout["close"], 2)
    if side > 0:
        # Fading a downward break: stop below the breakout bar's low.
        sl = math.floor((breakout["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        # Fading an upward break: stop above the breakout bar's high.
        sl = math.ceil((breakout["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Fade risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Fade risk too large versus price")

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
        "pattern": f"S220 {signal} Afternoon Break Fade {rr:g}R",
        "reason": (f"Fading a {range_size:.2f} micro-range break in the "
                   "afternoon reversion window"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
