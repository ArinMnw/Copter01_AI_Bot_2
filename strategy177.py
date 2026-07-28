# -*- coding: utf-8 -*-
"""S177 - Signed-volume/price divergence reclaim with a 7R target."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "DIVERGENCE_WINDOW": 48,
    "NET_MOVE_MIN_ATR": 0.60,
    "MAX_ALIGNED_DELTA_RATIO": 0.08,
    "EXTREME_LOOKBACK": 12,
    "EXHAUSTION_BODY_MIN_ATR": 0.30,
    "EXHAUSTION_VOLUME_QUANTILE": 0.70,
    "RECLAIM_CLOSE_EDGE": 0.60,
    "RECLAIM_VOLUME_QUANTILE": 0.45,
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


def detect_s177(rates, tf, dt_bkk, cfg):
    """Fade an extreme when signed tick-volume flow fails to confirm price."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(24, int(c["DIVERGENCE_WINDOW"]))
        extreme_lookback = max(5, int(c["EXTREME_LOOKBACK"]))
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
    net_move = history[-1]["close"] - history[0]["close"]
    if abs(net_move) < atr * float(c["NET_MOVE_MIN_ATR"]):
        return _wait("Price displacement is insufficient")
    regime_side = 1 if net_move > 0.0 else -1
    signed_volume = 0.0
    total_volume = 0.0
    for bar in history:
        volume = max(float(bar["tick_volume"]), 0.0)
        body = bar["close"] - bar["open"]
        signed_volume += (1.0 if body > 0.0 else -1.0 if body < 0.0 else 0.0) * volume
        total_volume += volume
    delta_ratio = signed_volume / max(total_volume, 1.0)
    aligned_delta = regime_side * delta_ratio
    if aligned_delta > float(c["MAX_ALIGNED_DELTA_RATIO"]):
        return _wait(f"Signed flow confirms price ({aligned_delta:.2f})")

    exhaustion = bars[-2]
    reclaim = bars[-1]
    exhaustion_body = exhaustion["close"] - exhaustion["open"]
    exhaustion_range = exhaustion["high"] - exhaustion["low"]
    if (exhaustion_range <= 0.0
            or regime_side * exhaustion_body < atr * float(c["EXHAUSTION_BODY_MIN_ATR"])):
        return _wait("No aligned exhaustion extension")
    prior = bars[-extreme_lookback - 2:-2]
    if regime_side > 0:
        made_extreme = exhaustion["high"] > max(bar["high"] for bar in prior)
    else:
        made_extreme = exhaustion["low"] < min(bar["low"] for bar in prior)
    if not made_extreme:
        return _wait("Exhaustion did not extend prior structure")
    exhaustion_volume_min = _quantile(
        [bar["tick_volume"] for bar in history], c["EXHAUSTION_VOLUME_QUANTILE"]
    )
    if exhaustion["tick_volume"] < exhaustion_volume_min:
        return _wait("Divergent extreme lacks exhaustion volume")

    reclaim_range = reclaim["high"] - reclaim["low"]
    if reclaim_range <= 0.0:
        return _wait("Reclaim range is zero")
    reclaim_location = (reclaim["close"] - reclaim["low"]) / reclaim_range
    exhaustion_midpoint = (exhaustion["open"] + exhaustion["close"]) * 0.50
    reclaim_volume_min = _quantile(
        [bar["tick_volume"] for bar in history], c["RECLAIM_VOLUME_QUANTILE"]
    )
    edge = float(c["RECLAIM_CLOSE_EDGE"])
    if regime_side < 0:
        side = 1
        confirmed = (reclaim["close"] > reclaim["open"]
                     and reclaim["close"] > exhaustion_midpoint
                     and reclaim_location >= edge)
    else:
        side = -1
        confirmed = (reclaim["close"] < reclaim["open"]
                     and reclaim["close"] < exhaustion_midpoint
                     and reclaim_location <= 1.0 - edge)
    if not confirmed or reclaim["tick_volume"] < reclaim_volume_min:
        return _wait("Signed-flow divergence lacks opposite reclaim")

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
        return _wait(f"Divergence-reclaim risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Divergence-reclaim risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S177 {signal} Signed-Flow Divergence {rr:g}R",
        "reason": (f"Price={net_move / atr:.2f}ATR, aligned delta={aligned_delta:.2f}; "
                   "divergent structural extreme reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
