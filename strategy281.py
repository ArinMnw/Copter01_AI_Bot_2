# -*- coding: utf-8 -*-
"""S281 - Lempel-Ziv high-complexity reclaim, optimized 27R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy280 import DEFAULT_CFG as S280_DEFAULT_CFG
from strategy280 import _lz_complexity


DEFAULT_CFG = {
    **S280_DEFAULT_CFG,
    "LZ_COMPLEXITY_MIN": 1.25,
    "SWEEP_LOOKBACK": 10,
    "REJECTION_WICK_MIN": 0.20,
    "RECLAIM_FRACTION_MIN": 0.15,
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    "TP_RR": 27.00,
    "BE_RR": 0.32,
}


def detect_s281(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a failed sweep in a high-complexity return-sign regime."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(32, int(c["LZ_LOOKBACK"]))
        complexity_min = float(c["LZ_COMPLEXITY_MIN"])
        balance_min = float(c["MIN_DIRECTION_BALANCE"])
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
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    signs = []
    for previous, current in zip(closes, closes[1:]):
        if current > previous:
            signs.append("1")
        elif current < previous:
            signs.append("0")
    if len(signs) < lookback * 0.75:
        return _wait("Too few non-zero returns for Lempel-Ziv state")
    positive_fraction = signs.count("1") / len(signs)
    if min(positive_fraction, 1.0 - positive_fraction) < balance_min:
        return _wait("Sign sequence is directionally degenerate")
    sequence = "".join(signs[-lookback:])
    normalized = _lz_complexity(sequence) * math.log2(len(sequence)) / len(sequence)
    if normalized < complexity_min:
        return _wait(f"Return-sign complexity is not high ({normalized:.2f})")

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
        "pattern": f"S281 {signal} LZ High-Complexity Reclaim {rr:g}R",
        "reason": (
            f"Failed sweep in high-complexity sign regime "
            f"(LZ={normalized:.2f})"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
