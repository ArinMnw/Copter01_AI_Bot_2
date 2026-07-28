# -*- coding: utf-8 -*-
"""S145 — Fade failed London-to-NY inventory reclaim with a short 7R stop."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy144 import DEFAULT_CFG as S144_DEFAULT_CFG
from strategy144 import detect_s144


DEFAULT_CFG = {
    "SOURCE_CFG": dict(S144_DEFAULT_CFG),
    "ATR_PERIOD": 14,
    "SL_WICK_BUFFER_ATR": 0.20,
    "MAX_RISK_PRICE_PCT": 0.25,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s145(rates, tf, dt_bkk, cfg):
    """Place an opposite wick-limit fade when S144 identifies an NY reclaim."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        source_cfg = dict(c.get("SOURCE_CFG") or {})
        period = max(1, int(c["ATR_PERIOD"]))
        buffer_atr = max(0.01, float(c["SL_WICK_BUFFER_ATR"]))
        max_risk_pct = float(c["MAX_RISK_PRICE_PCT"])
        rr = max(7.0, float(c["TP_RR"]))
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid config: {exc}")
    source = detect_s144(rates, tf, dt_bkk, source_cfg)
    if source.get("signal") not in ("BUY", "SELL"):
        return source
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        latest = bars[-1]
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid source data: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    direction = "SELL" if source["signal"] == "BUY" else "BUY"
    if direction == "SELL":
        entry = round(latest["high"], 2)
        sl = math.ceil((latest["high"] + atr * buffer_atr - 1e-12) * 100) / 100
        risk = sl - entry
        tp = math.floor((entry - rr * risk + 1e-12) * 100) / 100
    else:
        entry = round(latest["low"], 2)
        sl = math.floor((latest["low"] - atr * buffer_atr + 1e-12) * 100) / 100
        risk = entry - sl
        tp = math.ceil((entry + rr * risk - 1e-12) * 100) / 100
    if risk <= 0.0 or risk / entry * 100.0 > max_risk_pct:
        return _wait(f"Wick fade risk invalid or too large ({risk / entry * 100.0:.2f}%)")
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "order_type": "limit",
        "pattern": f"S145 {direction} NY Reclaim Fade {rr:g}R",
        "reason": (f"Fade S144 {source['signal']} reclaim at closed-bar wick; "
                   f"risk={risk / atr:.2f}ATR, target={rr:.2f}R"),
        "be_rr": float(c["BE_RR"]), "cancel_bars": int(c["CANCEL_BARS"]),
    }
