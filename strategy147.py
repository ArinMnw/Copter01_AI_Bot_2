# -*- coding: utf-8 -*-
"""S147 — S146 entropy release using conservative next-open market execution."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy146 import DEFAULT_CFG as S146_DEFAULT_CFG
from strategy146 import detect_s146


DEFAULT_CFG = {
    "S146_CFG": dict(S146_DEFAULT_CFG),
    "ATR_PERIOD": 14,
    "MAX_MARKET_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.40,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s147(rates, tf, dt_bkk, cfg):
    """Convert a closed S146 release into a next-bar-open market order."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        source_cfg = dict(c.get("S146_CFG") or {})
        period = max(1, int(c["ATR_PERIOD"]))
        rr = max(7.0, float(c["TP_RR"]))
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid config: {exc}")
    result = detect_s146(rates, tf, dt_bkk, source_cfg)
    if result.get("signal") not in ("BUY", "SELL"):
        return result
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        entry = round(bars[-1]["close"], 2)
        sl = float(result["sl"])
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid source data: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    direction = result["signal"]
    risk = entry - sl if direction == "BUY" else sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_MARKET_RISK_ATR"]):
        return _wait(f"Market release risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Market release risk too large versus price ({risk_pct:.2f}%)")
    raw_tp = entry + rr * risk if direction == "BUY" else entry - rr * risk
    tp = (math.ceil((raw_tp - 1e-12) * 100) / 100 if direction == "BUY"
          else math.floor((raw_tp + 1e-12) * 100) / 100)
    output = dict(result)
    output.update({
        "entry": entry, "tp": tp, "order_type": "market",
        "pattern": f"S147 {direction} Entropy Release Market {rr:g}R",
        "reason": f"Next-open execution test; {result.get('reason', '')}",
        "be_rr": float(c["BE_RR"]), "cancel_bars": None,
    })
    return output
