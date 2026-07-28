# -*- coding: utf-8 -*-
"""S173 - Upper-tail skewness exhaustion reclaim SELL, optimized 16.2R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile
from strategy172 import _skewness


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "TAIL_WINDOW": 64,
    "SKEWNESS_MIN": 0.25,
    "UPPER_TAIL_QUANTILE": 0.88,
    "EXHAUSTION_BODY_MIN_ATR": 0.35,
    "EXHAUSTION_CLOSE_LOCATION_MIN": 0.75,
    "EXHAUSTION_VOLUME_QUANTILE": 0.75,
    "RECLAIM_CLOSE_LOCATION_MAX": 0.38,
    "RECLAIM_VOLUME_QUANTILE": 0.45,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.30,
    "MAX_RISK_PRICE_PCT": 0.32,
    "TP_RR": 16.20,
    "BE_RR": 0.75,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s173(rates, tf, dt_bkk, cfg):
    """Sell a bearish reclaim after a closed upper-tail volume shock."""
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
    if skewness < float(c["SKEWNESS_MIN"]):
        return _wait(f"Upper-tail skewness is insufficient ({skewness:.2f})")
    upper_tail = _quantile(history_returns, c["UPPER_TAIL_QUANTILE"])

    exhaustion = bars[-2]
    reclaim = bars[-1]
    exhaustion_range = exhaustion["high"] - exhaustion["low"]
    exhaustion_body = exhaustion["close"] - exhaustion["open"]
    exhaustion_return = exhaustion["close"] - bars[-3]["close"]
    if exhaustion_range <= 0.0 or exhaustion_body < atr * float(c["EXHAUSTION_BODY_MIN_ATR"]):
        return _wait("No bullish tail-shock body")
    exhaustion_location = (exhaustion["close"] - exhaustion["low"]) / exhaustion_range
    if (exhaustion_return < upper_tail
            or exhaustion_location < float(c["EXHAUSTION_CLOSE_LOCATION_MIN"])):
        return _wait("Bullish bar is not an empirical upper-tail shock")
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
    if (reclaim["close"] >= reclaim["open"]
            or reclaim["close"] >= exhaustion_midpoint
            or reclaim_location > float(c["RECLAIM_CLOSE_LOCATION_MAX"])
            or reclaim["tick_volume"] < reclaim_volume_min):
        return _wait("No confirmed bearish reclaim after tail shock")

    fraction = float(c["ENTRY_RANGE_FRACTION"])
    entry = reclaim["low"] + fraction * reclaim_range
    if entry <= reclaim["close"]:
        return _wait("SELL limit is not above reclaim close")
    sl = max(exhaustion["high"], reclaim["high"]) + atr * float(c["SL_BUFFER_ATR"])
    entry = round(entry, 2)
    sl = math.ceil((sl - 1e-12) * 100.0) / 100.0
    risk = sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Tail-reclaim risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Tail-reclaim risk too large versus price ({risk_pct:.2f}%)")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry - rr * risk
    tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": "SELL",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S173 SELL Upper-Tail Reclaim {rr:g}R",
        "reason": (f"Return skew={skewness:.2f}, shock={exhaustion_return / atr:.2f}ATR; "
                   "high-volume upper-tail exhaustion reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
