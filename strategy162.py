# -*- coding: utf-8 -*-
"""S162 - Bearish VR follow-through, optimized target 70R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile
from strategy161 import _variance_ratio_two


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "VR_WINDOW": 64,
    "VR_MIN": 1.20,
    "BURST_BARS": 3,
    "BURST_MOVE_MIN_ATR": 0.90,
    "BURST_EFFICIENCY_MIN": 0.80,
    "BURST_CLOSE_LOCATION_MAX": 0.28,
    "BURST_VOLUME_QUANTILE": 0.65,
    "CONFIRM_CLOSE_LOCATION_MAX": 0.45,
    "CONFIRM_RETRACE_MAX": 0.50,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.20,
    "MAX_RISK_PRICE_PCT": 0.25,
    "TP_RR": 70.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s162(rates, tf, dt_bkk, cfg):
    """Wait one closed bar for acceptance after a persistent bearish burst."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(24, int(c["VR_WINDOW"]))
        burst_bars = max(2, int(c["BURST_BARS"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < window + burst_bars + period + 4 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-2], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    returns = [bars[index]["close"] - bars[index - 1]["close"]
               for index in range(1, len(bars))]
    regime_returns = returns[-window - burst_bars - 1:-burst_bars - 1]
    variance_ratio = _variance_ratio_two(regime_returns)
    if variance_ratio < float(c["VR_MIN"]):
        return _wait(f"Variance ratio is not persistent ({variance_ratio:.2f})")
    burst_returns = returns[-burst_bars - 1:-1]
    burst_move = sum(burst_returns)
    gross_move = sum(abs(value) for value in burst_returns)
    efficiency = abs(burst_move) / gross_move if gross_move > 0.0 else 0.0
    if burst_move > -atr * float(c["BURST_MOVE_MIN_ATR"]):
        return _wait("Prior bearish burst is too small")
    if efficiency < float(c["BURST_EFFICIENCY_MIN"]):
        return _wait("Prior bearish burst is not efficient")

    burst_bar = bars[-2]
    confirm = bars[-1]
    burst_range = burst_bar["high"] - burst_bar["low"]
    confirm_range = confirm["high"] - confirm["low"]
    if burst_range <= 0.0 or confirm_range <= 0.0:
        return _wait("Burst or confirmation range is zero")
    burst_location = (burst_bar["close"] - burst_bar["low"]) / burst_range
    if burst_bar["close"] >= burst_bar["open"] or burst_location > float(c["BURST_CLOSE_LOCATION_MAX"]):
        return _wait("Burst bar did not close near its low")
    history = bars[-window - 2:-2]
    volume_min = _quantile(
        [bar["tick_volume"] for bar in history], c["BURST_VOLUME_QUANTILE"]
    )
    if burst_bar["tick_volume"] < volume_min:
        return _wait("Burst volume is below empirical threshold")

    confirm_location = (confirm["close"] - confirm["low"]) / confirm_range
    acceptance_ceiling = burst_bar["close"] + float(c["CONFIRM_RETRACE_MAX"]) * (
        burst_bar["open"] - burst_bar["close"]
    )
    if (confirm["close"] >= burst_bar["close"]
            or confirm["close"] >= confirm["open"]
            or confirm_location > float(c["CONFIRM_CLOSE_LOCATION_MAX"])):
        return _wait("Next bar did not accept the bearish burst")

    fraction = float(c["ENTRY_RANGE_FRACTION"])
    entry = confirm["low"] + fraction * confirm_range
    if entry <= confirm["close"]:
        return _wait("SELL limit is not above confirmation close")
    sl = max(confirm["high"], acceptance_ceiling) + atr * float(c["SL_BUFFER_ATR"])
    entry = round(entry, 2)
    sl = math.ceil((sl - 1e-12) * 100.0) / 100.0
    risk = sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Follow-through risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Follow-through risk too large versus price ({risk_pct:.2f}%)")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry - rr * risk
    tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": "SELL",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S162 SELL VR Follow-Through {rr:g}R",
        "reason": (f"VR(2)={variance_ratio:.2f}, bearish burst={burst_move / atr:.2f}ATR, "
                   f"efficiency={efficiency:.2f}; next bar accepted lower"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
