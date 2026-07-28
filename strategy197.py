# -*- coding: utf-8 -*-
"""S197 - Permutation-entropy collapse structural-sweep reclaim, 16.9R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "PE_WINDOW": 96,
    "PE_ORDER": 3,
    "PE_MAX": 0.90,
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


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _log_returns(bars):
    values = []
    for index in range(1, len(bars)):
        previous = bars[index - 1]["close"]
        current = bars[index]["close"]
        if previous <= 0.0 or current <= 0.0:
            return []
        values.append(math.log(current / previous))
    return values


def _permutation_entropy(values, order):
    """Normalized Bandt-Pompe permutation entropy over ordinal patterns."""
    if len(values) < order + 1:
        return 1.0
    counts = {}
    total = 0
    for index in range(len(values) - order + 1):
        segment = values[index:index + order]
        pattern = tuple(sorted(range(order), key=lambda k: (segment[k], k)))
        counts[pattern] = counts.get(pattern, 0) + 1
        total += 1
    entropy = 0.0
    for count in counts.values():
        probability = count / total
        entropy -= probability * math.log(probability)
    return entropy / math.log(math.factorial(order))


def detect_s197(rates, tf, dt_bkk, cfg):
    """Fade a structural sweep only when ordinal price complexity has collapsed."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(40, int(c["PE_WINDOW"]))
        order = min(5, max(2, int(c["PE_ORDER"])))
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
    closes = [bar["close"] for bar in history]
    entropy = _permutation_entropy(closes, order)
    if entropy > float(c["PE_MAX"]):
        return _wait(f"Ordinal complexity is not collapsed (PE={entropy:.3f})")
    returns = _log_returns(history)
    if not returns:
        return _wait("Invalid return history")
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
        return _wait("Low-entropy shock lacks directional body")
    side = 1 if exhaustion_body < 0.0 else -1
    if side * shock_return >= 0.0:
        return _wait("Shock return and reversal side disagree")
    volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["EXHAUSTION_VOLUME_QUANTILE"]
    )
    if exhaustion["tick_volume"] < volume_floor:
        return _wait("Low-entropy shock lacks volume")

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
        return _wait("Low-entropy shock lacks confirmed reclaim")

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
        return _wait(f"Entropy-sweep risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Entropy-sweep risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S197 {signal} Entropy-Collapse Sweep {rr:g}R",
        "reason": (f"Permutation entropy={entropy:.3f} collapsed; "
                   "structural sweep reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
