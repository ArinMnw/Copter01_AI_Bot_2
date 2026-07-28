# -*- coding: utf-8 -*-
"""S151 — Fade the trapped S150 absorption breakout at its wick, 7R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy150 import DEFAULT_CFG as S150_DEFAULT_CFG
from strategy150 import detect_s150


DEFAULT_CFG = {
    "S150_CFG": dict(S150_DEFAULT_CFG),
    "ATR_PERIOD": 14,
    "SL_WICK_BUFFER_ATR": 0.20,
    "MAX_RISK_PRICE_PCT": 0.30,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s151(rates, tf, dt_bkk, cfg):
    """Place an opposite wick limit when S150 confirms a presumed trap."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        source_cfg = dict(c.get("S150_CFG") or {})
        period = max(1, int(c["ATR_PERIOD"]))
        buffer_atr = max(0.01, float(c["SL_WICK_BUFFER_ATR"]))
        rr = max(7.0, float(c["TP_RR"]))
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid config: {exc}")
    source = detect_s150(rates, tf, dt_bkk, source_cfg)
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
    risk_pct = risk / entry * 100.0 if risk > 0.0 else math.inf
    if risk <= 0.0 or risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Trap-fade risk invalid or too large ({risk_pct:.2f}%)")
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "order_type": "limit",
        "pattern": f"S151 {direction} Absorption Trap Fade {rr:g}R",
        "reason": (f"Fade S150 {source['signal']} confirmation at wick; "
                   f"risk={risk / atr:.2f}ATR"),
        "be_rr": float(c["BE_RR"]), "cancel_bars": int(c["CANCEL_BARS"]),
    }
