# -*- coding: utf-8 -*-
"""S208 - Weekend-gap continuation on the first post-gap bar, 10R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "GAP_HOURS_MIN": 24.0,
    "GAP_MIN_ATR": 0.50,
    "GAP_MAX_ATR": 8.00,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def detect_s208(rates, tf, dt_bkk, cfg):
    """Trade the weekend gap in its own direction off the first post-gap bar."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        gap_hours = float(c["GAP_HOURS_MIN"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < period + 6 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    first = bars[-1]
    last_pre_gap = bars[-2]
    elapsed_hours = (int(first["time"]) - int(last_pre_gap["time"])) / 3600.0
    if elapsed_hours < gap_hours:
        return _wait("No weekend time gap before this bar")
    gap = first["open"] - last_pre_gap["close"]
    gap_atr = abs(gap) / atr
    if gap_atr < float(c["GAP_MIN_ATR"]):
        return _wait(f"Weekend gap too small ({gap_atr:.2f} ATR)")
    if gap_atr > float(c["GAP_MAX_ATR"]):
        return _wait(f"Weekend gap too large ({gap_atr:.2f} ATR)")
    side = 1 if gap > 0.0 else -1

    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(first["close"], 2)
    if side > 0:
        sl = math.floor((first["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((first["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Gap risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Gap risk too large versus price")

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
        "order_type": "market",
        "pattern": f"S208 {signal} Weekend Gap Drive {rr:g}R",
        "reason": f"Weekend gap {gap:+.2f} ({gap_atr:.2f} ATR) continuation",
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
