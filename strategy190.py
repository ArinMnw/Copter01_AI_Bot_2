# -*- coding: utf-8 -*-
"""S190 - EVT Hill-tail structural-sweep reclaim, 7R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "TAIL_WINDOW": 96,
    "TAIL_K": 12,
    "EXCEEDANCE_PROB": 0.03,
    "MIN_HILL_GAMMA": 0.05,
    "MAX_HILL_GAMMA": 1.50,
    "TAIL_EXTENSION_ATR": 0.03,
    "STRUCTURE_LOOKBACK": 18,
    "SWEEP_BUFFER_ATR": 0.02,
    "EXHAUSTION_BODY_MIN_ATR": 0.28,
    "EXHAUSTION_VOLUME_QUANTILE": 0.55,
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


def detect_s190(rates, tf, dt_bkk, cfg):
    """Fade a structural sweep beyond an EVT Pareto return threshold."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(40, int(c["TAIL_WINDOW"]))
        tail_k = max(4, int(c["TAIL_K"]))
        exceedance_prob = float(c["EXCEEDANCE_PROB"])
        structure_lookback = max(4, int(c["STRUCTURE_LOOKBACK"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not 0.0 < exceedance_prob < 0.50:
        return _wait("EXCEEDANCE_PROB must be between 0 and 0.5")
    required = max(window + period + 4, structure_lookback + 4)
    if rates is None or len(rates) < required or dt_bkk is None:
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
    magnitudes = sorted((abs(value) for value in returns if abs(value) > 1e-12),
                        reverse=True)
    if len(magnitudes) <= tail_k:
        return _wait("Not enough nonzero returns for Hill tail estimate")
    threshold_base = magnitudes[tail_k]
    if threshold_base <= 0.0:
        return _wait("Hill threshold is zero")
    hill_gamma = sum(math.log(value / threshold_base)
                     for value in magnitudes[:tail_k]) / tail_k
    hill_gamma = min(float(c["MAX_HILL_GAMMA"]),
                     max(float(c["MIN_HILL_GAMMA"]), hill_gamma))
    empirical_tail_prob = tail_k / len(magnitudes)
    pareto_scale = max(1.0, empirical_tail_prob / exceedance_prob) ** hill_gamma
    evt_threshold = threshold_base * pareto_scale

    exhaustion = bars[-2]
    reclaim = bars[-1]
    exhaustion_return = exhaustion["close"] - history[-1]["close"]
    required_move = evt_threshold + atr * float(c["TAIL_EXTENSION_ATR"])
    if abs(exhaustion_return) <= required_move:
        return _wait(
            f"Return is below EVT threshold ({abs(exhaustion_return) / atr:.2f}<"
            f"{required_move / atr:.2f} ATR)"
        )
    side = 1 if exhaustion_return < 0.0 else -1
    exhaustion_body = exhaustion["close"] - exhaustion["open"]
    exhaustion_range = exhaustion["high"] - exhaustion["low"]
    if (exhaustion_range <= 0.0
            or side * exhaustion_body >= 0.0
            or abs(exhaustion_body) < atr * float(c["EXHAUSTION_BODY_MIN_ATR"])):
        return _wait("EVT exceedance lacks aligned exhaustion body")
    volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["EXHAUSTION_VOLUME_QUANTILE"]
    )
    if exhaustion["tick_volume"] < volume_floor:
        return _wait("EVT exceedance lacks exhaustion volume")

    structure = bars[-structure_lookback - 2:-2]
    buffer = atr * float(c["SWEEP_BUFFER_ATR"])
    if side > 0 and exhaustion["low"] >= min(bar["low"] for bar in structure) - buffer:
        return _wait("Lower EVT exceedance did not sweep structure")
    if side < 0 and exhaustion["high"] <= max(bar["high"] for bar in structure) + buffer:
        return _wait("Upper EVT exceedance did not sweep structure")

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
        return _wait("EVT structural sweep lacks confirmed reclaim")

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
        return _wait(f"EVT-reclaim risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"EVT-reclaim risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S190 {signal} EVT Hill Sweep {rr:g}R",
        "reason": (f"Return={abs(exhaustion_return) / atr:.2f} ATR exceeded EVT "
                   f"threshold={required_move / atr:.2f}, gamma={hill_gamma:.2f}; reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
