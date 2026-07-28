# -*- coding: utf-8 -*-
"""S148 — Entropy release market entry with range-reentry invalidation."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy146 import DEFAULT_CFG as S146_DEFAULT_CFG
from strategy146 import detect_s146


DEFAULT_CFG = {
    "S146_CFG": dict(S146_DEFAULT_CFG),
    "ATR_PERIOD": 14,
    "BOUNDARY_STOP_ATR": 0.15,
    "MAX_RISK_ATR": 1.25,
    "MAX_RISK_PRICE_PCT": 0.40,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s148(rates, tf, dt_bkk, cfg):
    """Enter next open and invalidate on a return through the broken boundary."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        source_cfg = dict(c.get("S146_CFG") or {})
        period = max(1, int(c["ATR_PERIOD"]))
        stop_atr = max(0.01, float(c["BOUNDARY_STOP_ATR"]))
        rr = max(7.0, float(c["TP_RR"]))
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid config: {exc}")
    source = detect_s146(rates, tf, dt_bkk, source_cfg)
    if source.get("signal") not in ("BUY", "SELL"):
        return source
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        entry = round(bars[-1]["close"], 2)
        boundary = float(source["entry"])
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid source data: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    direction = source["signal"]
    if direction == "BUY":
        sl = math.floor((boundary - atr * stop_atr + 1e-12) * 100) / 100
        risk = entry - sl
    else:
        sl = math.ceil((boundary + atr * stop_atr - 1e-12) * 100) / 100
        risk = sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Boundary market risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Boundary market risk too large versus price ({risk_pct:.2f}%)")
    raw_tp = entry + rr * risk if direction == "BUY" else entry - rr * risk
    tp = (math.ceil((raw_tp - 1e-12) * 100) / 100 if direction == "BUY"
          else math.floor((raw_tp + 1e-12) * 100) / 100)
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "order_type": "market",
        "pattern": f"S148 {direction} Entropy Boundary {rr:g}R",
        "reason": (f"Next-open entropy release; invalidation beyond boundary "
                   f"{boundary:.2f}, risk={risk / atr:.2f}ATR"),
        "be_rr": float(c["BE_RR"]), "cancel_bars": None,
    }
