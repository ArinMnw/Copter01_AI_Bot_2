# -*- coding: utf-8 -*-
"""S275 - DFA anti-persistent failed-sweep reclaim, optimized 20.8R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy274 import DEFAULT_CFG as S274_DEFAULT_CFG
from strategy274 import _dfa_alpha


DEFAULT_CFG = {
    **S274_DEFAULT_CFG,
    "DFA_ALPHA_MAX": 0.45,
    "SWEEP_LOOKBACK": 10,
    "REJECTION_WICK_MIN": 0.20,
    "RECLAIM_FRACTION_MIN": 0.15,
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    "TP_RR": 20.80,
    "BE_RR": 1.53,
}


def detect_s275(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a failed sweep in a multi-scale DFA anti-persistent regime."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(64, int(c["DFA_LOOKBACK"]))
        scales = tuple(sorted({max(4, int(value)) for value in c["DFA_SCALES"]}))
        alpha_max = float(c["DFA_ALPHA_MAX"])
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
        closes = [bar["close"] for bar in bars[-lookback - 1:-1]]
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
    alpha = _dfa_alpha(returns, scales)
    if alpha is None:
        return _wait("DFA exponent is unavailable")
    if alpha > alpha_max:
        return _wait(f"DFA regime is not anti-persistent (alpha={alpha:.2f})")

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
        "pattern": f"S275 {signal} DFA Anti-Persistent Reclaim {rr:g}R",
        "reason": (
            f"Failed sweep in multi-scale DFA anti-persistent regime "
            f"(alpha={alpha:.2f})"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
