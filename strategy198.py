# -*- coding: utf-8 -*-
"""S198 - Runs-test excess-alternation structural-sweep reclaim, 16.9R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile
from strategy197 import _log_returns, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "RUNS_WINDOW": 96,
    "RUNS_Z_MIN": 1.20,
    "RETURN_QUANTILE": 0.70,
    "STRUCTURE_LOOKBACK": 18,
    "SWEEP_BUFFER_ATR": 0.02,
    "EXHAUSTION_BODY_MIN_ATR": 0.28,
    "EXHAUSTION_VOLUME_QUANTILE": 0.50,
    "RECLAIM_CLOSE_EDGE": 0.58,
    "RECLAIM_VOLUME_QUANTILE": 0.35,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.35,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 16.90,
    "BE_RR": 0.75,
    "CANCEL_BARS": 4,
}


def _runs_z_score(returns):
    """Wald-Wolfowitz runs z-score; positive means excess sign alternation."""
    signs = [1 if value > 0.0 else -1 for value in returns if value != 0.0]
    positives = sum(1 for sign in signs if sign > 0)
    negatives = len(signs) - positives
    if positives < 2 or negatives < 2:
        return 0.0
    runs = 1 + sum(1 for index in range(1, len(signs))
                   if signs[index] != signs[index - 1])
    total = positives + negatives
    expected = 2.0 * positives * negatives / total + 1.0
    variance = (2.0 * positives * negatives
                * (2.0 * positives * negatives - total)
                / (total * total * (total - 1.0)))
    if variance <= 0.0:
        return 0.0
    return (runs - expected) / math.sqrt(variance)


def detect_s198(rates, tf, dt_bkk, cfg):
    """Fade a structural sweep only when return signs alternate in excess."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(40, int(c["RUNS_WINDOW"]))
        structure_lookback = max(4, int(c["STRUCTURE_LOOKBACK"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
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
    returns = _log_returns(history)
    if not returns:
        return _wait("Invalid return history")
    runs_z = _runs_z_score(returns)
    if runs_z < float(c["RUNS_Z_MIN"]):
        return _wait(f"Sign sequence lacks excess alternation (z={runs_z:.2f})")
    return_floor = _quantile([abs(value) for value in returns], c["RETURN_QUANTILE"])

    exhaustion = bars[-2]
    reclaim = bars[-1]
    previous_close = history[-1]["close"]
    if previous_close <= 0.0 or exhaustion["close"] <= 0.0:
        return _wait("Non-positive price")
    shock_return = math.log(exhaustion["close"] / previous_close)
    if abs(shock_return) < return_floor:
        return _wait("Exhaustion return is not locally extreme")
    exhaustion_body = exhaustion["close"] - exhaustion["open"]
    exhaustion_range = exhaustion["high"] - exhaustion["low"]
    if (exhaustion_range <= 0.0
            or abs(exhaustion_body) < atr * float(c["EXHAUSTION_BODY_MIN_ATR"])):
        return _wait("Alternation shock lacks directional body")
    side = 1 if exhaustion_body < 0.0 else -1
    if side * shock_return >= 0.0:
        return _wait("Shock return and reversal side disagree")
    volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["EXHAUSTION_VOLUME_QUANTILE"]
    )
    if exhaustion["tick_volume"] < volume_floor:
        return _wait("Alternation shock lacks volume")

    structure = bars[-structure_lookback - 2:-2]
    buffer = atr * float(c["SWEEP_BUFFER_ATR"])
    if side > 0 and exhaustion["low"] >= min(bar["low"] for bar in structure) - buffer:
        return _wait("Lower shock did not sweep structure")
    if side < 0 and exhaustion["high"] <= max(bar["high"] for bar in structure) + buffer:
        return _wait("Upper shock did not sweep structure")

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
        return _wait("Alternation shock lacks confirmed reclaim")

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
        return _wait(f"Runs-sweep risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Runs-sweep risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S198 {signal} Runs-Alternation Sweep {rr:g}R",
        "reason": (f"Runs z={runs_z:.2f} excess alternation; "
                   "structural sweep reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
