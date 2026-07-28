# -*- coding: utf-8 -*-
"""S163 - Variance-ratio bearish burst, failed rally, and rejection, 7R."""

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
    "BURST_MOVE_MIN_ATR": 0.85,
    "BURST_EFFICIENCY_MIN": 0.78,
    "PULLBACK_MIN_FRACTION": 0.10,
    "PULLBACK_MAX_FRACTION": 0.70,
    "REJECTION_CLOSE_LOCATION_MAX": 0.38,
    "REJECTION_VOLUME_QUANTILE": 0.50,
    "ENTRY_RANGE_FRACTION": 0.40,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.20,
    "MAX_RISK_PRICE_PCT": 0.30,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s163(rates, tf, dt_bkk, cfg):
    """Sell a rejected rally inside a serially persistent bearish regime."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(24, int(c["VR_WINDOW"]))
        burst_bars = max(2, int(c["BURST_BARS"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < window + burst_bars + period + 5 or dt_bkk is None:
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
    regime_returns = returns[-window - burst_bars - 2:-burst_bars - 2]
    variance_ratio = _variance_ratio_two(regime_returns)
    if variance_ratio < float(c["VR_MIN"]):
        return _wait(f"Variance ratio is not persistent ({variance_ratio:.2f})")
    burst_returns = returns[-burst_bars - 2:-2]
    burst_move = sum(burst_returns)
    gross_move = sum(abs(value) for value in burst_returns)
    efficiency = abs(burst_move) / gross_move if gross_move > 0.0 else 0.0
    if burst_move > -atr * float(c["BURST_MOVE_MIN_ATR"]):
        return _wait("Bearish burst is too small")
    if efficiency < float(c["BURST_EFFICIENCY_MIN"]):
        return _wait("Bearish burst is not efficient")

    pullback = bars[-2]
    rejection = bars[-1]
    pullback_move = pullback["close"] - pullback["open"]
    if pullback_move <= 0.0:
        return _wait("No bullish pullback after the burst")
    pullback_fraction = pullback_move / abs(burst_move)
    if not (float(c["PULLBACK_MIN_FRACTION"]) <= pullback_fraction
            <= float(c["PULLBACK_MAX_FRACTION"])):
        return _wait(f"Pullback fraction outside range ({pullback_fraction:.2f})")

    rejection_range = rejection["high"] - rejection["low"]
    if rejection_range <= 0.0:
        return _wait("Rejection range is zero")
    rejection_location = (rejection["close"] - rejection["low"]) / rejection_range
    if (rejection["close"] >= rejection["open"]
            or rejection["close"] >= pullback["open"]
            or rejection_location > float(c["REJECTION_CLOSE_LOCATION_MAX"])):
        return _wait("Pullback did not close a bearish rejection")
    history = bars[-window - 2:-2]
    volume_min = _quantile(
        [bar["tick_volume"] for bar in history], c["REJECTION_VOLUME_QUANTILE"]
    )
    if rejection["tick_volume"] < volume_min:
        return _wait("Rejection volume is below empirical threshold")

    fraction = float(c["ENTRY_RANGE_FRACTION"])
    entry = rejection["low"] + fraction * rejection_range
    if entry <= rejection["close"]:
        return _wait("SELL limit is not above rejection close")
    sl = max(pullback["high"], rejection["high"]) + atr * float(c["SL_BUFFER_ATR"])
    entry = round(entry, 2)
    sl = math.ceil((sl - 1e-12) * 100.0) / 100.0
    risk = sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Failed-rally risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Failed-rally risk too large versus price ({risk_pct:.2f}%)")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry - rr * risk
    tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": "SELL",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S163 SELL VR Failed Rally {rr:g}R",
        "reason": (f"VR(2)={variance_ratio:.2f}, burst={burst_move / atr:.2f}ATR, "
                   f"pullback={pullback_fraction:.2f}; bearish rejection"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
