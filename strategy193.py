# -*- coding: utf-8 -*-
"""S193 - Bipower jump-variation structural-sweep reclaim, 16.9R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "JUMP_WINDOW": 72,
    "JUMP_SCORE_MIN": 4.00,
    "JUMP_SHARE_MIN": 0.55,
    "STRUCTURE_LOOKBACK": 20,
    "SWEEP_BUFFER_ATR": 0.02,
    "EXHAUSTION_BODY_MIN_ATR": 0.30,
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


def _log_returns(bars):
    values = []
    for index in range(1, len(bars)):
        previous = bars[index - 1]["close"]
        current = bars[index]["close"]
        if previous <= 0.0 or current <= 0.0:
            return []
        values.append(math.log(current / previous))
    return values


def _bipower_variation(returns):
    """Per-bar continuous-variance proxy robust to isolated price jumps."""
    if len(returns) < 2:
        return 0.0
    products = [abs(returns[index]) * abs(returns[index - 1])
                for index in range(1, len(returns))]
    return math.pi * 0.50 * sum(products) / len(products)


def detect_s193(rates, tf, dt_bkk, cfg):
    """Fade a structural sweep whose return is discontinuous versus bipower variance."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(30, int(c["JUMP_WINDOW"]))
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
    continuous_variance = _bipower_variation(returns)
    if continuous_variance <= 0.0:
        return _wait("Bipower variation is zero")

    exhaustion = bars[-2]
    reclaim = bars[-1]
    previous_close = history[-1]["close"]
    if previous_close <= 0.0 or exhaustion["close"] <= 0.0:
        return _wait("Non-positive price")
    shock_return = math.log(exhaustion["close"] / previous_close)
    shock_variance = shock_return * shock_return
    jump_score = shock_variance / continuous_variance
    jump_share = max(0.0, shock_variance - continuous_variance) / max(
        shock_variance, 1e-18
    )
    if (jump_score < float(c["JUMP_SCORE_MIN"])
            or jump_share < float(c["JUMP_SHARE_MIN"])):
        return _wait(
            f"No discontinuous jump (score={jump_score:.2f}, share={jump_share:.2f})"
        )

    exhaustion_body = exhaustion["close"] - exhaustion["open"]
    exhaustion_range = exhaustion["high"] - exhaustion["low"]
    if (exhaustion_range <= 0.0
            or abs(exhaustion_body) < atr * float(c["EXHAUSTION_BODY_MIN_ATR"])):
        return _wait("Jump lacks directional exhaustion body")
    side = 1 if exhaustion_body < 0.0 else -1
    if side * shock_return >= 0.0:
        return _wait("Jump return and reversal side disagree")
    volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["EXHAUSTION_VOLUME_QUANTILE"]
    )
    if exhaustion["tick_volume"] < volume_floor:
        return _wait("Jump lacks exhaustion volume")

    structure = bars[-structure_lookback - 2:-2]
    buffer = atr * float(c["SWEEP_BUFFER_ATR"])
    if side > 0 and exhaustion["low"] >= min(bar["low"] for bar in structure) - buffer:
        return _wait("Lower jump did not sweep structure")
    if side < 0 and exhaustion["high"] <= max(bar["high"] for bar in structure) + buffer:
        return _wait("Upper jump did not sweep structure")

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
        return _wait("Jump lacks confirmed reclaim")

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
        return _wait(f"Jump-sweep risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Jump-sweep risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S193 {signal} Bipower Jump Sweep {rr:g}R",
        "reason": (f"Bipower jump score={jump_score:.2f}, share={jump_share:.2f}; "
                   "structural sweep reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
