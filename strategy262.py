# -*- coding: utf-8 -*-
"""S262 - Bayesian sign-switching failed-sweep reclaim, optimized 27R.

When closed-bar return signs exhibit a high posterior switching probability,
directional range excursions are more likely to mean-revert.  S262 waits for a
fresh local high/low sweep that closes back inside the range, then trades the
reclaim with the event extreme as a short structural stop.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy261 import DEFAULT_CFG as S261_DEFAULT_CFG


DEFAULT_CFG = {
    **S261_DEFAULT_CFG,
    "SWITCH_PROBABILITY_MIN": 0.58,
    "MIN_TRANSITIONS": 32,
    "SWEEP_LOOKBACK": 10,
    "REJECTION_WICK_MIN": 0.20,
    "RECLAIM_FRACTION_MIN": 0.15,
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    "TP_RR": 27.00,
    "BE_RR": 0.43,
}


def _switch_posterior(signs, prior):
    switches = sum(
        1 for previous, current in zip(signs, signs[1:])
        if previous != current
    )
    total = len(signs) - 1
    probability = (switches + prior) / (total + 2.0 * prior)
    return probability, total


def detect_s262(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a failed sweep in a Bayesian anti-persistent sign regime."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(16, int(c["MARKOV_LOOKBACK"]))
        sweep_lookback = max(3, int(c["SWEEP_LOOKBACK"]))
        period = max(1, int(c["ATR_PERIOD"]))
        prior = float(c["BETA_PRIOR"])
        threshold = float(c["SWITCH_PROBABILITY_MIN"])
        min_transitions = max(4, int(c["MIN_TRANSITIONS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(lookback + 3, sweep_lookback + 2, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if prior <= 0.0 or not 0.5 <= threshold < 1.0:
        return _wait("Invalid Markov posterior parameters")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")

    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [bar["close"] for bar in bars[-lookback - 2:-1]]
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
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
    signs = [1 if value > 0.0 else -1 if value < 0.0 else 0 for value in returns]
    signs = [value for value in signs if value]
    probability, transitions = _switch_posterior(signs[-lookback:], prior)
    if transitions < min_transitions:
        return _wait(f"Too few Markov transitions ({transitions})")
    if probability < threshold:
        return _wait(f"Sign-switch probability is weak ({probability:.2f})")

    event = bars[-1]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Event candle has zero range")
    prior_bars = bars[-sweep_lookback - 1:-1]
    prior_high = max(bar["high"] for bar in prior_bars)
    prior_low = min(bar["low"] for bar in prior_bars)
    range_width = prior_high - prior_low
    if range_width <= 0.0:
        return _wait("Prior range is degenerate")
    wick_min = float(c["REJECTION_WICK_MIN"])
    reclaim_min = float(c["RECLAIM_FRACTION_MIN"])
    lower_wick = min(event["open"], event["close"]) - event["low"]
    upper_wick = event["high"] - max(event["open"], event["close"])
    if (
        event["low"] < prior_low
        and event["close"] > prior_low + reclaim_min * range_width
        and event["close"] > event["open"]
        and lower_wick / event_range >= wick_min
    ):
        signal, side = "BUY", 1
    elif (
        event["high"] > prior_high
        and event["close"] < prior_high - reclaim_min * range_width
        and event["close"] < event["open"]
        and upper_wick / event_range >= wick_min
    ):
        signal, side = "SELL", -1
    else:
        return _wait("No failed structural sweep and reclaim")
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled by direction-survival filter")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled by direction-survival filter")

    entry = round(event["close"], 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor((event["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Reclaim risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Reclaim risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Reclaim risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    if side > 0:
        tp = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
    else:
        tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S262 {signal} Markov Switch Sweep Reclaim {rr:g}R",
        "reason": (
            f"Failed sweep in anti-persistent regime "
            f"(switch posterior={probability:.2f})"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
