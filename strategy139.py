# -*- coding: utf-8 -*-
"""S139 — First failed downside reclaim within three closed bars, SELL 7R."""

from __future__ import annotations

import math
from datetime import datetime

from strategy119 import _atr, _bars
from strategy120 import detect_s120


DEFAULT_CFG = {
    "SOURCE_CFG": {"RV_EXPANSION_MIN": 2.00, "PREVIOUS_RV_MAX": 1.00,
                   "MAX_RISK_ATR": 2.50},
    "ATR_PERIOD": 14,
    "FAIL_WITHIN_BARS": 3,
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


def detect_s139(rates, tf, dt_bkk, cfg):
    """Detect the first closed reclaim failure no more than three bars later."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    if rates is None or len(rates) < 110 or dt_bkk is None or dt_bkk.tzinfo is None:
        return _wait("Not enough data or timezone-aware dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], max(1, int(c["ATR_PERIOD"])))
        within = max(1, int(c["FAIL_WITHIN_BARS"]))
        rr = max(7.0, float(c["TP_RR"]))
        source_cfg = dict(c.get("SOURCE_CFG") or {})
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid input: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    latest = bars[-1]
    body = latest["open"] - latest["close"]
    if body < atr * float(c["FAIL_BODY_MIN_ATR"]):
        return _wait("Latest bar is not a bearish failure close")
    matched = None
    for lag in range(1, within + 1):
        source_rates = rates[:-lag]
        reversal = bars[-lag - 1]
        source_dt = datetime.fromtimestamp(reversal["time"], tz=dt_bkk.tzinfo)
        source = detect_s120(source_rates, tf, source_dt, source_cfg)
        if source.get("signal") != "BUY":
            continue
        fail_level = reversal["low"] - atr * float(c["FAIL_CLOSE_BUFFER_ATR"])
        intermediate = bars[-lag:-1]
        if any(bar["close"] < fail_level for bar in intermediate):
            continue
        if latest["close"] < fail_level:
            matched = (lag, reversal)
            break
    if matched is None:
        return _wait("No first downside-reclaim failure within allowed bars")

    lag, reversal = matched
    entry = round(reversal["low"], 2)
    if entry <= latest["close"]:
        return _wait("SELL retest limit is not above failure close")
    sl = math.ceil((reversal["high"] + atr * float(c["SL_REVERSAL_BUFFER_ATR"]) - 1e-12)
                   * 100) / 100
    risk = sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Failure structure risk outside range ({risk / atr:.2f} ATR)")
    tp = math.floor((entry - rr * risk + 1e-12) * 100) / 100
    return {
        "signal": "SELL", "entry": entry, "sl": sl, "tp": tp,
        "order_type": "limit",
        "pattern": f"S139 SELL Failed Reclaim {rr:g}R",
        "reason": (f"First failure {lag} bar(s) after downside reversal; "
                   f"body={body / atr:.2f}ATR, risk={risk / atr:.2f}ATR"),
        "be_rr": float(c["BE_RR"]), "cancel_bars": int(c["CANCEL_BARS"]),
    }
