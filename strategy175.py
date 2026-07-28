# -*- coding: utf-8 -*-
"""S175 - Amihud liquidity-vacuum reclaim with a 7R target."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "IMPACT_WINDOW": 64,
    "IMPACT_QUANTILE": 0.88,
    "SHOCK_BODY_MIN_ATR": 0.35,
    "SHOCK_VOLUME_QUANTILE_MAX": 0.70,
    "SHOCK_CLOSE_EDGE": 0.70,
    "RECLAIM_CLOSE_EDGE": 0.62,
    "RECLAIM_VOLUME_QUANTILE": 0.50,
    "RECLAIM_VOLUME_RATIO_MIN": 1.05,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.30,
    "MAX_RISK_PRICE_PCT": 0.32,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s175(rates, tf, dt_bkk, cfg):
    """Fade an abnormal price-impact shock after liquidity-backed reclaim."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(24, int(c["IMPACT_WINDOW"]))
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
    impacts = []
    for index in range(1, len(history)):
        move = abs(history[index]["close"] - history[index - 1]["close"])
        impacts.append(move / max(float(history[index]["tick_volume"]), 1.0))
    impact_min = _quantile(impacts, c["IMPACT_QUANTILE"])
    volume_max = _quantile(
        [bar["tick_volume"] for bar in history], c["SHOCK_VOLUME_QUANTILE_MAX"]
    )

    shock = bars[-2]
    reclaim = bars[-1]
    shock_return = shock["close"] - bars[-3]["close"]
    shock_body = shock["close"] - shock["open"]
    shock_range = shock["high"] - shock["low"]
    shock_impact = abs(shock_return) / max(float(shock["tick_volume"]), 1.0)
    if shock_range <= 0.0 or abs(shock_body) < atr * float(c["SHOCK_BODY_MIN_ATR"]):
        return _wait("No directional liquidity shock")
    shock_location = (shock["close"] - shock["low"]) / shock_range
    edge = float(c["SHOCK_CLOSE_EDGE"])
    aligned_edge = shock_location >= edge if shock_return > 0.0 else shock_location <= 1.0 - edge
    if (shock_impact < impact_min or shock["tick_volume"] > volume_max
            or shock_return * shock_body <= 0.0 or not aligned_edge):
        return _wait("Closed bar is not a low-liquidity impact shock")

    reclaim_range = reclaim["high"] - reclaim["low"]
    if reclaim_range <= 0.0:
        return _wait("Reclaim range is zero")
    reclaim_location = (reclaim["close"] - reclaim["low"]) / reclaim_range
    shock_midpoint = (shock["open"] + shock["close"]) * 0.50
    reclaim_volume_min = _quantile(
        [bar["tick_volume"] for bar in history], c["RECLAIM_VOLUME_QUANTILE"]
    )
    reclaim_edge = float(c["RECLAIM_CLOSE_EDGE"])
    if shock_return < 0.0:
        side = 1
        confirmed = (reclaim["close"] > reclaim["open"]
                     and reclaim["close"] > shock_midpoint
                     and reclaim_location >= reclaim_edge)
    else:
        side = -1
        confirmed = (reclaim["close"] < reclaim["open"]
                     and reclaim["close"] < shock_midpoint
                     and reclaim_location <= 1.0 - reclaim_edge)
    restored_volume = (reclaim["tick_volume"] >= reclaim_volume_min
                       and reclaim["tick_volume"] >= shock["tick_volume"]
                       * float(c["RECLAIM_VOLUME_RATIO_MIN"]))
    if not confirmed or not restored_volume:
        return _wait("Impact shock lacks liquidity-backed opposite reclaim")

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
        return _wait(f"Impact-reclaim risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Impact-reclaim risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S175 {signal} Liquidity Vacuum {rr:g}R",
        "reason": (f"Impact={shock_impact / max(impact_min, 1e-12):.2f}x tail; "
                   "low-liquidity displacement reclaimed on restored volume"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
