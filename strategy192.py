# -*- coding: utf-8 -*-
"""S192 - EWMA volatility-of-volatility structural-sweep reclaim, 16.9R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "VOL_WINDOW": 96,
    "FAST_VOL_SPAN": 8,
    "SLOW_VOL_SPAN": 40,
    "VOL_RATIO_MIN": 1.30,
    "VOL_RATIO_JUMP_MIN": 0.08,
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
    "TP_RR": 16.90,
    "BE_RR": 0.52,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _true_ranges(bars):
    values = []
    for index in range(1, len(bars)):
        bar = bars[index]
        previous_close = bars[index - 1]["close"]
        values.append(max(
            bar["high"] - bar["low"],
            abs(bar["high"] - previous_close),
            abs(bar["low"] - previous_close),
        ))
    return values


def _ewma(values, alpha):
    if not values:
        return 0.0
    estimate = values[0]
    for value in values[1:]:
        estimate = alpha * value + (1.0 - alpha) * estimate
    return estimate


def detect_s192(rates, tf, dt_bkk, cfg):
    """Fade a structural sweep that creates an abrupt EWMA volatility shock."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(40, int(c["VOL_WINDOW"]))
        fast_span = max(2, int(c["FAST_VOL_SPAN"]))
        slow_span = max(fast_span + 1, int(c["SLOW_VOL_SPAN"]))
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
    true_ranges = _true_ranges(history)
    if not true_ranges:
        return _wait("True-range history is empty")
    fast_alpha = 2.0 / (fast_span + 1.0)
    slow_alpha = 2.0 / (slow_span + 1.0)
    fast_before = _ewma(true_ranges, fast_alpha)
    slow_before = _ewma(true_ranges, slow_alpha)
    if slow_before <= 0.0:
        return _wait("Slow EWMA volatility is zero")

    exhaustion = bars[-2]
    reclaim = bars[-1]
    previous_close = history[-1]["close"]
    exhaustion_tr = max(
        exhaustion["high"] - exhaustion["low"],
        abs(exhaustion["high"] - previous_close),
        abs(exhaustion["low"] - previous_close),
    )
    fast_after = fast_alpha * exhaustion_tr + (1.0 - fast_alpha) * fast_before
    slow_after = slow_alpha * exhaustion_tr + (1.0 - slow_alpha) * slow_before
    ratio_before = fast_before / slow_before
    ratio_after = fast_after / max(slow_after, 1e-12)
    ratio_jump = ratio_after - ratio_before
    if (ratio_after < float(c["VOL_RATIO_MIN"])
            or ratio_jump < float(c["VOL_RATIO_JUMP_MIN"])):
        return _wait(
            f"No EWMA volatility shock (ratio={ratio_after:.2f}, jump={ratio_jump:.2f})"
        )

    exhaustion_body = exhaustion["close"] - exhaustion["open"]
    exhaustion_range = exhaustion["high"] - exhaustion["low"]
    if (exhaustion_range <= 0.0
            or abs(exhaustion_body) < atr * float(c["EXHAUSTION_BODY_MIN_ATR"])):
        return _wait("Volatility shock lacks directional exhaustion body")
    side = 1 if exhaustion_body < 0.0 else -1
    volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["EXHAUSTION_VOLUME_QUANTILE"]
    )
    if exhaustion["tick_volume"] < volume_floor:
        return _wait("Volatility shock lacks exhaustion volume")
    structure = bars[-structure_lookback - 2:-2]
    buffer = atr * float(c["SWEEP_BUFFER_ATR"])
    if side > 0 and exhaustion["low"] >= min(bar["low"] for bar in structure) - buffer:
        return _wait("Lower volatility shock did not sweep structure")
    if side < 0 and exhaustion["high"] <= max(bar["high"] for bar in structure) + buffer:
        return _wait("Upper volatility shock did not sweep structure")

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
        return _wait("Volatility shock lacks confirmed reclaim")

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
        return _wait(f"Vol-shock risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Vol-shock risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S192 {signal} EWMA Vol-Shock Sweep {rr:g}R",
        "reason": (f"Fast/slow TR ratio={ratio_after:.2f}, jump={ratio_jump:.2f}; "
                   "structural liquidation sweep reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
