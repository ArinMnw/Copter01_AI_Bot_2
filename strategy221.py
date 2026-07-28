# -*- coding: utf-8 -*-
"""S221 - Rollover momentum run with an expanding-body trigger, 10R.

Keeps the one proven edge source in this project (the 04-06 BKK rollover clock,
see S206) but replaces the trigger geometry. S206 fires on a single close beyond
a micro-range, which a one-off spike can satisfy. S221 instead requires a *run*:
N consecutive closes in the same direction whose bodies are expanding. The
mechanism it is betting on is sustained settlement flow rather than a single
print — a different signature, so it can win or lose independently of S206
rather than being a relabelled version of it.

Stop is the run's own recent structure (previous bars' extreme) so risk stays
short and the payoff clears the project's RR>=7 bar.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 4,
    "SESSION_END_HOUR": 6,
    "RUN_BARS": 3,
    "EXPANDING_BODIES": True,
    "RUN_MIN_ATR": 0.60,
    "LAST_BODY_MIN_FRACTION": 0.50,
    "SL_LOOKBACK_BARS": 2,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s221(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Join a directional run of expanding bodies inside the rollover window."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        run_bars = max(2, int(c["RUN_BARS"]))
        sl_lookback = max(1, int(c["SL_LOOKBACK_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = run_bars + sl_lookback + period + 6
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside rollover session window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    run = bars[-run_bars:]
    bodies = [bar["close"] - bar["open"] for bar in run]
    if all(body > 0.0 for body in bodies):
        side = 1
    elif all(body < 0.0 for body in bodies):
        side = -1
    else:
        return _wait("No unbroken directional run")

    magnitudes = [abs(body) for body in bodies]
    if c["EXPANDING_BODIES"]:
        for index in range(1, len(magnitudes)):
            if magnitudes[index] <= magnitudes[index - 1]:
                return _wait("Run bodies are not expanding")
    run_move = abs(run[-1]["close"] - run[0]["open"])
    if run_move < atr * float(c["RUN_MIN_ATR"]):
        return _wait(f"Run is too small ({run_move / atr:.2f} ATR)")
    last = run[-1]
    last_range = last["high"] - last["low"]
    if last_range <= 0.0 or magnitudes[-1] < last_range * float(
            c["LAST_BODY_MIN_FRACTION"]):
        return _wait("Final run bar lacks body conviction")

    structure = bars[-run_bars - sl_lookback:-1]
    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(last["close"], 2)
    if side > 0:
        sl_raw = min(bar["low"] for bar in structure[-sl_lookback:]) - buffer
        sl = math.floor((sl_raw + 1e-12) * 100.0) / 100.0
    else:
        sl_raw = max(bar["high"] for bar in structure[-sl_lookback:]) + buffer
        sl = math.ceil((sl_raw - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Run risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Run risk too large versus price")

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
        "pattern": f"S221 {signal} Rollover Momentum Run {rr:g}R",
        "reason": (f"{run_bars}-bar expanding run of {run_move / atr:.2f} ATR "
                   "inside the rollover window"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
