# -*- coding: utf-8 -*-
"""S174 - Bipower jump-exhaustion reclaim, optimized 9R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "JUMP_WINDOW": 48,
    "JUMP_SHARE_MIN": 0.16,
    "SHOCK_QUANTILE": 0.88,
    "SHOCK_BODY_MIN_ATR": 0.35,
    "SHOCK_VOLUME_QUANTILE": 0.75,
    "RECLAIM_CLOSE_EDGE": 0.62,
    "RECLAIM_VOLUME_QUANTILE": 0.45,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.30,
    "MAX_RISK_PRICE_PCT": 0.32,
    "TP_RR": 9.00,
    "BE_RR": 0.38,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s174(rates, tf, dt_bkk, cfg):
    """Fade a closed high-volume jump only after an opposite reclaim closes."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(24, int(c["JUMP_WINDOW"]))
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
    returns = [history[index]["close"] - history[index - 1]["close"]
               for index in range(1, len(history))]
    realized_variance = sum(value * value for value in returns)
    bipower = (math.pi / 2.0) * sum(
        abs(returns[index]) * abs(returns[index - 1])
        for index in range(1, len(returns))
    )
    jump_share = max(0.0, realized_variance - bipower) / max(realized_variance, 1e-12)
    if jump_share < float(c["JUMP_SHARE_MIN"]):
        return _wait(f"No discontinuous-volatility regime (jump={jump_share:.2f})")

    shock = bars[-2]
    reclaim = bars[-1]
    shock_return = shock["close"] - bars[-3]["close"]
    shock_body = shock["close"] - shock["open"]
    shock_range = shock["high"] - shock["low"]
    if shock_range <= 0.0 or abs(shock_body) < atr * float(c["SHOCK_BODY_MIN_ATR"]):
        return _wait("No directional jump body")
    shock_abs_min = _quantile([abs(value) for value in returns], c["SHOCK_QUANTILE"])
    if abs(shock_return) < shock_abs_min or shock_return * shock_body <= 0.0:
        return _wait("Closed bar is not an aligned empirical jump")
    shock_volume_min = _quantile(
        [bar["tick_volume"] for bar in history], c["SHOCK_VOLUME_QUANTILE"]
    )
    if shock["tick_volume"] < shock_volume_min:
        return _wait("Jump lacks exhaustion volume")

    reclaim_range = reclaim["high"] - reclaim["low"]
    if reclaim_range <= 0.0:
        return _wait("Reclaim range is zero")
    reclaim_location = (reclaim["close"] - reclaim["low"]) / reclaim_range
    shock_midpoint = (shock["open"] + shock["close"]) * 0.50
    reclaim_volume_min = _quantile(
        [bar["tick_volume"] for bar in history], c["RECLAIM_VOLUME_QUANTILE"]
    )
    close_edge = float(c["RECLAIM_CLOSE_EDGE"])
    if shock_return < 0.0:
        side = 1
        confirmed = (reclaim["close"] > reclaim["open"]
                     and reclaim["close"] > shock_midpoint
                     and reclaim_location >= close_edge)
    else:
        side = -1
        confirmed = (reclaim["close"] < reclaim["open"]
                     and reclaim["close"] < shock_midpoint
                     and reclaim_location <= 1.0 - close_edge)
    if not confirmed or reclaim["tick_volume"] < reclaim_volume_min:
        return _wait("Jump was not reclaimed on confirmed opposite flow")

    fraction = float(c["ENTRY_RANGE_FRACTION"])
    if side > 0:
        entry = reclaim["high"] - fraction * reclaim_range
        if entry >= reclaim["close"]:
            return _wait("BUY limit is not below reclaim close")
        sl = min(shock["low"], reclaim["low"]) - atr * float(c["SL_BUFFER_ATR"])
        entry = round(entry, 2)
        sl = math.floor((sl + 1e-12) * 100.0) / 100.0
    else:
        entry = reclaim["low"] + fraction * reclaim_range
        if entry <= reclaim["close"]:
            return _wait("SELL limit is not above reclaim close")
        sl = max(shock["high"], reclaim["high"]) + atr * float(c["SL_BUFFER_ATR"])
        entry = round(entry, 2)
        sl = math.ceil((sl - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Jump-reclaim risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Jump-reclaim risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S174 {signal} Bipower Jump Reclaim {rr:g}R",
        "reason": (f"Jump share={jump_share:.2f}, shock={shock_return / atr:.2f}ATR; "
                   "high-volume discontinuity reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
