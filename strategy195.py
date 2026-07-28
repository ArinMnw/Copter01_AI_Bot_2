# -*- coding: utf-8 -*-
"""S195 - Amihud liquidity-impact breakout acceptance continuation, 7R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile
from strategy194 import _return_and_illiquidity


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "ILLIQ_WINDOW": 96,
    "ILLIQ_QUANTILE": 0.90,
    "ILLIQ_MULT_MIN": 1.05,
    "RETURN_QUANTILE": 0.70,
    "STRUCTURE_LOOKBACK": 18,
    "BREAK_CLOSE_BUFFER_ATR": 0.01,
    "SHOCK_BODY_MIN_ATR": 0.35,
    "SHOCK_VOLUME_MAX_QUANTILE": 0.75,
    "HOLD_TOLERANCE_ATR": 0.10,
    "HOLD_CLOSE_EDGE": 0.55,
    "HOLD_VOLUME_QUANTILE": 0.30,
    "ENTRY_RANGE_FRACTION": 0.55,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.60,
    "MAX_RISK_PRICE_PCT": 0.40,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s195(rates, tf, dt_bkk, cfg):
    """Follow a high-impact structural break only after price accepts beyond it."""
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

    shock = bars[-2]
    hold = bars[-1]
    previous_close = history[-1]["close"]
    if previous_close <= 0.0 or shock["close"] <= 0.0:
        return _wait("Non-positive price")
    shock_return = math.log(shock["close"] / previous_close)
    absolute_return = abs(shock_return)
    shock_illiquidity = absolute_return / max(float(shock["tick_volume"]), 1.0)
    impact_ratio = shock_illiquidity / illiquidity_floor
    if (impact_ratio < float(c["ILLIQ_MULT_MIN"])
            or absolute_return < return_floor):
        return _wait(f"No liquidity impact breakout (impact={impact_ratio:.2f})")

    shock_body = shock["close"] - shock["open"]
    shock_range = shock["high"] - shock["low"]
    if (shock_range <= 0.0
            or abs(shock_body) < atr * float(c["SHOCK_BODY_MIN_ATR"])):
        return _wait("Impact shock lacks directional body")
    side = 1 if shock_body > 0.0 else -1
    if side * shock_return <= 0.0:
        return _wait("Impact return and body direction disagree")
    volume_ceiling = _quantile(
        [bar["tick_volume"] for bar in history], c["SHOCK_VOLUME_MAX_QUANTILE"]
    )
    if shock["tick_volume"] > volume_ceiling:
        return _wait("Breakout impact did not occur in relatively thin liquidity")

    structure = bars[-structure_lookback - 2:-2]
    structure_high = max(bar["high"] for bar in structure)
    structure_low = min(bar["low"] for bar in structure)
    close_buffer = atr * float(c["BREAK_CLOSE_BUFFER_ATR"])
    if side > 0:
        breakout_level = structure_high
        if shock["close"] <= breakout_level + close_buffer:
            return _wait("Bullish impact did not close above structure")
    else:
        breakout_level = structure_low
        if shock["close"] >= breakout_level - close_buffer:
            return _wait("Bearish impact did not close below structure")

    hold_range = hold["high"] - hold["low"]
    if hold_range <= 0.0:
        return _wait("Acceptance range is zero")
    hold_location = (hold["close"] - hold["low"]) / hold_range
    tolerance = atr * float(c["HOLD_TOLERANCE_ATR"])
    edge = float(c["HOLD_CLOSE_EDGE"])
    if side > 0:
        accepted = (hold["low"] >= breakout_level - tolerance
                    and hold["close"] > breakout_level
                    and hold_location >= edge)
    else:
        accepted = (hold["high"] <= breakout_level + tolerance
                    and hold["close"] < breakout_level
                    and hold_location <= 1.0 - edge)
    volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["HOLD_VOLUME_QUANTILE"]
    )
    if not accepted or hold["tick_volume"] < volume_floor:
        return _wait("Breakout was not accepted beyond structure")

    fraction = float(c["ENTRY_RANGE_FRACTION"])
    if side > 0:
        entry = hold["high"] - fraction * hold_range
        if entry >= hold["close"]:
            return _wait("BUY limit is not below acceptance close")
        sl = min(shock["low"], hold["low"], breakout_level) - atr * float(
            c["SL_BUFFER_ATR"]
        )
        entry = round(entry, 2)
        sl = math.floor((sl + 1e-12) * 100.0) / 100.0
    else:
        entry = hold["low"] + fraction * hold_range
        if entry <= hold["close"]:
            return _wait("SELL limit is not above acceptance close")
        sl = max(shock["high"], hold["high"], breakout_level) + atr * float(
            c["SL_BUFFER_ATR"]
        )
        entry = round(entry, 2)
        sl = math.ceil((sl - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Liquidity-break risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Liquidity-break risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S195 {signal} Liquidity Break Accept {rr:g}R",
        "reason": (f"Amihud impact ratio={impact_ratio:.2f}; "
                   "structural breakout accepted"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
