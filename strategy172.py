# -*- coding: utf-8 -*-
"""S172 - Lower-tail skewness exhaustion reclaim BUY, optimized 10.8R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "TAIL_WINDOW": 64,
    "SKEWNESS_MAX": -0.25,
    "LOWER_TAIL_QUANTILE": 0.12,
    "EXHAUSTION_BODY_MIN_ATR": 0.35,
    "EXHAUSTION_CLOSE_LOCATION_MAX": 0.25,
    "EXHAUSTION_VOLUME_QUANTILE": 0.75,
    "RECLAIM_CLOSE_LOCATION_MIN": 0.62,
    "RECLAIM_VOLUME_QUANTILE": 0.45,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.30,
    "MAX_RISK_PRICE_PCT": 0.32,
    "TP_RR": 10.80,
    "BE_RR": 0.75,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _skewness(values):
    if len(values) < 8:
        return 0.0
    mean = sum(values) / len(values)
    second = sum((value - mean) ** 2 for value in values) / len(values)
    if second <= 1e-18:
        return 0.0
    third = sum((value - mean) ** 3 for value in values) / len(values)
    return third / (second ** 1.5)


def detect_s172(rates, tf, dt_bkk, cfg):
    """Buy a bullish reclaim after a closed lower-tail volume shock."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(24, int(c["TAIL_WINDOW"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
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
    history_returns = [history[index]["close"] - history[index - 1]["close"]
                       for index in range(1, len(history))]
    skewness = _skewness(history_returns)
    if skewness > float(c["SKEWNESS_MAX"]):
        return _wait(f"Lower-tail skewness is insufficient ({skewness:.2f})")
    lower_tail = _quantile(history_returns, c["LOWER_TAIL_QUANTILE"])

    exhaustion = bars[-2]
    reclaim = bars[-1]
    exhaustion_range = exhaustion["high"] - exhaustion["low"]
    exhaustion_body = exhaustion["open"] - exhaustion["close"]
    exhaustion_return = exhaustion["close"] - bars[-3]["close"]
    if exhaustion_range <= 0.0 or exhaustion_body < atr * float(c["EXHAUSTION_BODY_MIN_ATR"]):
        return _wait("No bearish tail-shock body")
    exhaustion_location = (exhaustion["close"] - exhaustion["low"]) / exhaustion_range
    if (exhaustion_return > lower_tail
            or exhaustion_location > float(c["EXHAUSTION_CLOSE_LOCATION_MAX"])):
        return _wait("Bearish bar is not an empirical lower-tail shock")
    exhaustion_volume_min = _quantile(
        [bar["tick_volume"] for bar in history], c["EXHAUSTION_VOLUME_QUANTILE"]
    )
    if exhaustion["tick_volume"] < exhaustion_volume_min:
        return _wait("Tail shock lacks capitulation volume")

    reclaim_range = reclaim["high"] - reclaim["low"]
    if reclaim_range <= 0.0:
        return _wait("Reclaim range is zero")
    reclaim_location = (reclaim["close"] - reclaim["low"]) / reclaim_range
    exhaustion_midpoint = (exhaustion["open"] + exhaustion["close"]) * 0.50
    reclaim_volume_min = _quantile(
        [bar["tick_volume"] for bar in history], c["RECLAIM_VOLUME_QUANTILE"]
    )
    if (reclaim["close"] <= reclaim["open"]
            or reclaim["close"] <= exhaustion_midpoint
            or reclaim_location < float(c["RECLAIM_CLOSE_LOCATION_MIN"])
            or reclaim["tick_volume"] < reclaim_volume_min):
        return _wait("No confirmed bullish reclaim after tail shock")

    fraction = float(c["ENTRY_RANGE_FRACTION"])
    entry = reclaim["high"] - fraction * reclaim_range
    if entry >= reclaim["close"]:
        return _wait("BUY limit is not below reclaim close")
    sl = min(exhaustion["low"], reclaim["low"]) - atr * float(c["SL_BUFFER_ATR"])
    entry = round(entry, 2)
    sl = math.floor((sl + 1e-12) * 100.0) / 100.0
    risk = entry - sl
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Tail-reclaim risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Tail-reclaim risk too large versus price ({risk_pct:.2f}%)")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + rr * risk
    tp = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
    return {
        "signal": "BUY",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S172 BUY Lower-Tail Reclaim {rr:g}R",
        "reason": (f"Return skew={skewness:.2f}, shock={exhaustion_return / atr:.2f}ATR; "
                   "high-volume lower-tail exhaustion reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
