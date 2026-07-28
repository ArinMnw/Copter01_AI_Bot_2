# -*- coding: utf-8 -*-
"""S166 - Upside-semivariance capitulation reclaim SELL, optimized 16R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SEMIVAR_WINDOW": 48,
    "UPSIDE_RATIO_MIN": 1.60,
    "NET_MOVE_MIN_ATR": 0.40,
    "EXHAUSTION_BODY_MIN_ATR": 0.35,
    "EXHAUSTION_CLOSE_LOCATION_MIN": 0.75,
    "EXHAUSTION_VOLUME_QUANTILE": 0.80,
    "RECLAIM_CLOSE_LOCATION_MAX": 0.35,
    "RECLAIM_VOLUME_QUANTILE": 0.55,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.30,
    "MAX_RISK_PRICE_PCT": 0.32,
    "TP_RR": 16.00,
    "BE_RR": 0.75,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s166(rates, tf, dt_bkk, cfg):
    """Sell a closed bearish reclaim after upside-semivariance capitulation."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(20, int(c["SEMIVAR_WINDOW"]))
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

    returns = [bars[index]["close"] - bars[index - 1]["close"]
               for index in range(1, len(bars))]
    regime = returns[-window - 2:-2]
    downside = sum(value * value for value in regime if value < 0.0) / window
    upside = sum(value * value for value in regime if value > 0.0) / window
    semivar_ratio = upside / max(downside, 1e-12)
    net_move = sum(regime)
    if semivar_ratio < float(c["UPSIDE_RATIO_MIN"]):
        return _wait(f"Upside semivariance is not dominant ({semivar_ratio:.2f})")
    if net_move < atr * float(c["NET_MOVE_MIN_ATR"]):
        return _wait("Regime net move is not bullish enough")

    exhaustion = bars[-2]
    reclaim = bars[-1]
    exhaustion_range = exhaustion["high"] - exhaustion["low"]
    reclaim_range = reclaim["high"] - reclaim["low"]
    exhaustion_body = exhaustion["close"] - exhaustion["open"]
    if exhaustion_range <= 0.0 or reclaim_range <= 0.0:
        return _wait("Exhaustion or reclaim range is zero")
    exhaustion_location = (exhaustion["close"] - exhaustion["low"]) / exhaustion_range
    if (exhaustion_body < atr * float(c["EXHAUSTION_BODY_MIN_ATR"])
            or exhaustion_location < float(c["EXHAUSTION_CLOSE_LOCATION_MIN"])):
        return _wait("Prior bar was not bullish capitulation")
    history = bars[-window - 2:-2]
    exhaustion_volume_min = _quantile(
        [bar["tick_volume"] for bar in history], c["EXHAUSTION_VOLUME_QUANTILE"]
    )
    reclaim_volume_min = _quantile(
        [bar["tick_volume"] for bar in history], c["RECLAIM_VOLUME_QUANTILE"]
    )
    if exhaustion["tick_volume"] < exhaustion_volume_min:
        return _wait("Capitulation volume is below empirical threshold")

    reclaim_location = (reclaim["close"] - reclaim["low"]) / reclaim_range
    exhaustion_midpoint = (exhaustion["open"] + exhaustion["close"]) * 0.50
    if (reclaim["close"] >= reclaim["open"]
            or reclaim["close"] >= exhaustion_midpoint
            or reclaim_location > float(c["RECLAIM_CLOSE_LOCATION_MAX"])
            or reclaim["tick_volume"] < reclaim_volume_min):
        return _wait("No bearish reclaim after capitulation")

    fraction = float(c["ENTRY_RANGE_FRACTION"])
    entry = reclaim["low"] + fraction * reclaim_range
    if entry <= reclaim["close"]:
        return _wait("SELL limit is not above reclaim close")
    sl = max(exhaustion["high"], reclaim["high"]) + atr * float(c["SL_BUFFER_ATR"])
    entry = round(entry, 2)
    sl = math.ceil((sl - 1e-12) * 100.0) / 100.0
    risk = sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Capitulation-reclaim risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Capitulation-reclaim risk too large versus price ({risk_pct:.2f}%)")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry - rr * risk
    tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": "SELL",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S166 SELL Semivariance Capitulation {rr:g}R",
        "reason": (f"Up/down semivariance={semivar_ratio:.2f}, net={net_move / atr:.2f}ATR; "
                   "high-volume capitulation reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
