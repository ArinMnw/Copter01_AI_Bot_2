# -*- coding: utf-8 -*-
"""S138 — Failed downside-capitulation reclaim continuation SELL, 7R."""

from __future__ import annotations

import math
from datetime import datetime

from strategy119 import _atr, _bars
from strategy120 import detect_s120


DEFAULT_CFG = {
    "SOURCE_CFG": {
        "RV_EXPANSION_MIN": 2.00,
        "PREVIOUS_RV_MAX": 1.00,
        "MAX_RISK_ATR": 2.50,
    },
    "ATR_PERIOD": 14,
    "FAIL_CLOSE_BUFFER_ATR": 0.02,
    "FAIL_BODY_MIN_ATR": 0.10,
    "SL_REVERSAL_BUFFER_ATR": 0.15,
    "MAX_RISK_ATR": 1.75,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s138(rates, tf, dt_bkk, cfg):
    """SELL the first closed failure below a downside-reversal candle."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    if rates is None or len(rates) < 100 or dt_bkk is None or dt_bkk.tzinfo is None:
        return _wait("Not enough data or timezone-aware dt_bkk missing")
    try:
        bars = _bars(rates)
        period = max(1, int(c["ATR_PERIOD"]))
        atr = _atr(bars[:-1], period)
        rr = max(7.0, float(c["TP_RR"]))
        previous_dt = datetime.fromtimestamp(bars[-2]["time"], tz=dt_bkk.tzinfo)
        source_cfg = dict(c.get("SOURCE_CFG") or {})
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid input: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    source = detect_s120(rates[:-1], tf, previous_dt, source_cfg)
    if source.get("signal") != "BUY":
        return _wait(f"No prior downside-capitulation reversal: {source.get('reason', 'WAIT')}")
    reversal, latest = bars[-2], bars[-1]
    body = latest["open"] - latest["close"]
    fail_level = reversal["low"] - atr * float(c["FAIL_CLOSE_BUFFER_ATR"])
    if latest["close"] >= fail_level or body < atr * float(c["FAIL_BODY_MIN_ATR"]):
        return _wait("Bullish capitulation reclaim has not failed")

    entry = round(reversal["low"], 2)
    if entry <= latest["close"]:
        return _wait("SELL retest limit is not above failure close")
    raw_sl = reversal["high"] + atr * float(c["SL_REVERSAL_BUFFER_ATR"])
    sl = math.ceil((raw_sl - 1e-12) * 100) / 100
    risk = sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Failure structure risk outside range ({risk / atr:.2f} ATR)")
    raw_tp = entry - rr * risk
    tp = math.floor((raw_tp + 1e-12) * 100) / 100
    return {
        "signal": "SELL", "entry": entry, "sl": sl, "tp": tp,
        "order_type": "limit",
        "pattern": f"S138 SELL Failed Capitulation {rr:g}R",
        "reason": (f"Prior downside RV reversal failed below {reversal['low']:.2f}; "
                   f"failure body={body / atr:.2f}ATR, risk={risk / atr:.2f}ATR"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
