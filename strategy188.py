# -*- coding: utf-8 -*-
"""S188 - Empirical expected-shortfall return-tail reclaim, 7R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "TAIL_WINDOW": 72,
    "TAIL_QUANTILE": 0.90,
    "ES_EXTENSION_ATR": 0.05,
    "EXHAUSTION_BODY_MIN_ATR": 0.28,
    "EXHAUSTION_VOLUME_QUANTILE": 0.60,
    "RECLAIM_CLOSE_EDGE": 0.58,
    "RECLAIM_VOLUME_QUANTILE": 0.35,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.35,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s188(rates, tf, dt_bkk, cfg):
    """Fade a closed return beyond its empirical expected-shortfall tail."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(32, int(c["TAIL_WINDOW"]))
        tail_q = float(c["TAIL_QUANTILE"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not 0.50 < tail_q < 1.0:
        return _wait("TAIL_QUANTILE must be between 0.5 and 1")
    if rates is None or len(rates) < window + period + 4 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-2], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    history = bars[-window - 2:-2]
    returns = [history[index]["close"] - history[index - 1]["close"]
               for index in range(1, len(history))]
    lower_var = _quantile(returns, 1.0 - tail_q)
    upper_var = _quantile(returns, tail_q)
    lower_tail = [value for value in returns if value <= lower_var]
    upper_tail = [value for value in returns if value >= upper_var]
    if not lower_tail or not upper_tail:
        return _wait("Expected-shortfall tails are empty")
    lower_es = sum(lower_tail) / len(lower_tail)
    upper_es = sum(upper_tail) / len(upper_tail)

    exhaustion = bars[-2]
    reclaim = bars[-1]
    exhaustion_return = exhaustion["close"] - history[-1]["close"]
    extension = atr * float(c["ES_EXTENSION_ATR"])
    if exhaustion_return < lower_es - extension:
        side = 1
        tail_level = lower_es
    elif exhaustion_return > upper_es + extension:
        side = -1
        tail_level = upper_es
    else:
        return _wait(
            f"Return is inside expected-shortfall tails ({exhaustion_return / atr:.2f} ATR)"
        )
    exhaustion_body = exhaustion["close"] - exhaustion["open"]
    exhaustion_range = exhaustion["high"] - exhaustion["low"]
    if (exhaustion_range <= 0.0
            or side * exhaustion_body >= 0.0
            or abs(exhaustion_body) < atr * float(c["EXHAUSTION_BODY_MIN_ATR"])):
        return _wait("Expected-shortfall breach lacks aligned exhaustion body")
    volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["EXHAUSTION_VOLUME_QUANTILE"]
    )
    if exhaustion["tick_volume"] < volume_floor:
        return _wait("Expected-shortfall breach lacks exhaustion volume")

    reclaim_range = reclaim["high"] - reclaim["low"]
    if reclaim_range <= 0.0:
        return _wait("Reclaim range is zero")
    reclaim_location = (reclaim["close"] - reclaim["low"]) / reclaim_range
    exhaustion_midpoint = (exhaustion["open"] + exhaustion["close"]) * 0.50
    reclaim_volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["RECLAIM_VOLUME_QUANTILE"]
    )
    edge = float(c["RECLAIM_CLOSE_EDGE"])
    if side > 0:
        confirmed = (reclaim["close"] > reclaim["open"]
                     and reclaim["close"] > exhaustion_midpoint
                     and reclaim_location >= edge)
    else:
        confirmed = (reclaim["close"] < reclaim["open"]
                     and reclaim["close"] < exhaustion_midpoint
                     and reclaim_location <= 1.0 - edge)
    if not confirmed or reclaim["tick_volume"] < reclaim_volume_floor:
        return _wait("Expected-shortfall breach lacks confirmed reclaim")

    fraction = float(c["ENTRY_RANGE_FRACTION"])
    if side > 0:
        entry = reclaim["high"] - fraction * reclaim_range
        if entry >= reclaim["close"]:
            return _wait("BUY limit is not below reclaim close")
        sl = min(exhaustion["low"], reclaim["low"]) - atr * float(c["SL_BUFFER_ATR"])
        entry = round(entry, 2)
        sl = math.floor((sl + 1e-12) * 100.0) / 100.0
    else:
        entry = reclaim["low"] + fraction * reclaim_range
        if entry <= reclaim["close"]:
            return _wait("SELL limit is not above reclaim close")
        sl = max(exhaustion["high"], reclaim["high"]) + atr * float(c["SL_BUFFER_ATR"])
        entry = round(entry, 2)
        sl = math.ceil((sl - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"ES-reclaim risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"ES-reclaim risk too large versus price ({risk_pct:.2f}%)")

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
        "order_type": "limit",
        "pattern": f"S188 {signal} Expected-Shortfall Reclaim {rr:g}R",
        "reason": (f"Return={exhaustion_return / atr:.2f} ATR breached empirical "
                   f"ES={tail_level / atr:.2f} ATR and reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
