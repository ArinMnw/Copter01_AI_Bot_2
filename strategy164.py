# -*- coding: utf-8 -*-
"""S164 - Downside-semivariance weak-rally rejection with a 7R target."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SEMIVAR_WINDOW": 48,
    "DOWNSIDE_RATIO_MIN": 1.60,
    "NET_MOVE_MIN_ATR": 0.40,
    "PULLBACK_BODY_MIN_ATR": 0.08,
    "PULLBACK_BODY_MAX_ATR": 0.65,
    "REJECTION_CLOSE_LOCATION_MAX": 0.40,
    "REJECTION_VOLUME_QUANTILE": 0.50,
    "ENTRY_RANGE_FRACTION": 0.45,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.20,
    "MAX_RISK_PRICE_PCT": 0.30,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s164(rates, tf, dt_bkk, cfg):
    """Sell a weak rally rejected inside a downside-semivariance regime."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(20, int(c["SEMIVAR_WINDOW"]))
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

    returns = [bars[index]["close"] - bars[index - 1]["close"]
               for index in range(1, len(bars))]
    regime = returns[-window - 2:-2]
    downside = sum(value * value for value in regime if value < 0.0) / window
    upside = sum(value * value for value in regime if value > 0.0) / window
    semivar_ratio = downside / max(upside, 1e-12)
    net_move = sum(regime)
    if semivar_ratio < float(c["DOWNSIDE_RATIO_MIN"]):
        return _wait(f"Downside semivariance is not dominant ({semivar_ratio:.2f})")
    if net_move > -atr * float(c["NET_MOVE_MIN_ATR"]):
        return _wait("Regime net move is not bearish enough")

    pullback = bars[-2]
    rejection = bars[-1]
    pullback_body = pullback["close"] - pullback["open"]
    if not (atr * float(c["PULLBACK_BODY_MIN_ATR"]) <= pullback_body
            <= atr * float(c["PULLBACK_BODY_MAX_ATR"])):
        return _wait("No bounded bullish pullback")
    rejection_range = rejection["high"] - rejection["low"]
    if rejection_range <= 0.0:
        return _wait("Rejection range is zero")
    rejection_location = (rejection["close"] - rejection["low"]) / rejection_range
    if (rejection["close"] >= rejection["open"]
            or rejection["close"] >= pullback["open"]
            or rejection_location > float(c["REJECTION_CLOSE_LOCATION_MAX"])):
        return _wait("Weak rally was not rejected")
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
        return _wait(f"Semivariance-rejection risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Semivariance-rejection risk too large versus price ({risk_pct:.2f}%)")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry - rr * risk
    tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": "SELL",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S164 SELL Downside Semivariance {rr:g}R",
        "reason": (f"Down/up semivariance={semivar_ratio:.2f}, net={net_move / atr:.2f}ATR; "
                   "weak rally rejected"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
