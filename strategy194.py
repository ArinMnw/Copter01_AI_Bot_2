# -*- coding: utf-8 -*-
"""S194 - Amihud liquidity-dislocation structural-sweep reclaim, 7R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "ILLIQ_WINDOW": 96,
    "ILLIQ_QUANTILE": 0.90,
    "ILLIQ_MULT_MIN": 1.05,
    "RETURN_QUANTILE": 0.70,
    "STRUCTURE_LOOKBACK": 18,
    "SWEEP_BUFFER_ATR": 0.02,
    "EXHAUSTION_BODY_MIN_ATR": 0.28,
    "EXHAUSTION_VOLUME_MAX_QUANTILE": 0.72,
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


def _return_and_illiquidity(bars):
    returns = []
    illiquidity = []
    for index in range(1, len(bars)):
        previous = bars[index - 1]["close"]
        current = bars[index]["close"]
        if previous <= 0.0 or current <= 0.0:
            return [], []
        absolute_return = abs(math.log(current / previous))
        volume = max(float(bars[index]["tick_volume"]), 1.0)
        returns.append(absolute_return)
        illiquidity.append(absolute_return / volume)
    return returns, illiquidity


def detect_s194(rates, tf, dt_bkk, cfg):
    """Fade a structural sweep caused by unusually high price impact per volume."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(40, int(c["ILLIQ_WINDOW"]))
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
    returns, illiquidity = _return_and_illiquidity(history)
    if not returns or not illiquidity:
        return _wait("Invalid return or liquidity history")
    illiquidity_floor = _quantile(illiquidity, c["ILLIQ_QUANTILE"])
    return_floor = _quantile(returns, c["RETURN_QUANTILE"])
    if illiquidity_floor <= 0.0:
        return _wait("Historical illiquidity is zero")

    exhaustion = bars[-2]
    reclaim = bars[-1]
    previous_close = history[-1]["close"]
    if previous_close <= 0.0 or exhaustion["close"] <= 0.0:
        return _wait("Non-positive price")
    shock_return = math.log(exhaustion["close"] / previous_close)
    absolute_return = abs(shock_return)
    shock_illiquidity = absolute_return / max(
        float(exhaustion["tick_volume"]), 1.0
    )
    impact_ratio = shock_illiquidity / illiquidity_floor
    if (impact_ratio < float(c["ILLIQ_MULT_MIN"])
            or absolute_return < return_floor):
        return _wait(
            f"No liquidity dislocation (impact={impact_ratio:.2f}, "
            f"return={absolute_return:.5f})"
        )

    exhaustion_body = exhaustion["close"] - exhaustion["open"]
    exhaustion_range = exhaustion["high"] - exhaustion["low"]
    if (exhaustion_range <= 0.0
            or abs(exhaustion_body) < atr * float(c["EXHAUSTION_BODY_MIN_ATR"])):
        return _wait("Liquidity shock lacks directional exhaustion body")
    side = 1 if exhaustion_body < 0.0 else -1
    if side * shock_return >= 0.0:
        return _wait("Liquidity shock return and reversal side disagree")
    volume_ceiling = _quantile(
        [bar["tick_volume"] for bar in history],
        c["EXHAUSTION_VOLUME_MAX_QUANTILE"],
    )
    if exhaustion["tick_volume"] > volume_ceiling:
        return _wait("Price impact did not occur in relatively thin liquidity")

    structure = bars[-structure_lookback - 2:-2]
    buffer = atr * float(c["SWEEP_BUFFER_ATR"])
    if side > 0 and exhaustion["low"] >= min(bar["low"] for bar in structure) - buffer:
        return _wait("Lower liquidity shock did not sweep structure")
    if side < 0 and exhaustion["high"] <= max(bar["high"] for bar in structure) + buffer:
        return _wait("Upper liquidity shock did not sweep structure")

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
        return _wait("Liquidity shock lacks confirmed reclaim")

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
        return _wait(f"Liquidity-shock risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Liquidity-shock risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S194 {signal} Liquidity-Impact Sweep {rr:g}R",
        "reason": (f"Amihud impact ratio={impact_ratio:.2f}; "
                   "thin-liquidity structural sweep reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
