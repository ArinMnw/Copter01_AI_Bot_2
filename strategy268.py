# -*- coding: utf-8 -*-
"""S268 - Wald-Wolfowitz anti-runs failed-sweep reclaim, optimized 27R.

A significantly positive runs statistic means return signs alternate more often
than independent signs would imply.  In that anti-persistent regime, S268 fades
a fresh local-range sweep only after the event candle closes back inside the
range, using the sweep extreme as a short structural stop.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy232 import DEFAULT_CFG as S232_DEFAULT_CFG
from strategy267 import _runs_zscore


DEFAULT_CFG = {
    **S232_DEFAULT_CFG,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "RUNS_LOOKBACK": 64,
    "RUNS_Z_MIN": 1.20,
    "MIN_SIGN_COUNT": 12,
    "SWEEP_LOOKBACK": 10,
    "REJECTION_WICK_MIN": 0.20,
    "RECLAIM_FRACTION_MIN": 0.15,
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    "TP_RR": 27.00,
    "BE_RR": 0.43,
}


def detect_s268(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a failed sweep in a statistically anti-persistent runs regime."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(24, int(c["RUNS_LOOKBACK"]))
        z_min = float(c["RUNS_Z_MIN"])
        min_count = max(2, int(c["MIN_SIGN_COUNT"]))
        sweep_lookback = max(3, int(c["SWEEP_LOOKBACK"]))
        period = max(1, int(c["ATR_PERIOD"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(lookback + 3, sweep_lookback + 2, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")

    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [bar["close"] for bar in bars[-lookback - 2:-1]]
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    signs = []
    for previous, current in zip(closes, closes[1:]):
        if current > previous:
            signs.append(1)
        elif current < previous:
            signs.append(-1)
    zscore, positive, negative = _runs_zscore(signs[-lookback:])
    if zscore is None or min(positive, negative) < min_count:
        return _wait("Runs test lacks balanced sign sample")
    if zscore < z_min:
        return _wait(f"Return runs are not anti-persistent (z={zscore:.2f})")

    event = bars[-1]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Event candle has zero range")
    prior = bars[-sweep_lookback - 1:-1]
    prior_high = max(bar["high"] for bar in prior)
    prior_low = min(bar["low"] for bar in prior)
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
        "pattern": f"S268 {signal} Anti-Runs Sweep Reclaim {rr:g}R",
        "reason": (
            f"Failed sweep in Wald-Wolfowitz anti-persistent regime "
            f"(z={zscore:.2f})"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
