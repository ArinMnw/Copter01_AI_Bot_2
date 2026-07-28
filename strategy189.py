# -*- coding: utf-8 -*-
"""S189 - Expected-shortfall structural-sweep reclaim, 16.9R."""

from __future__ import annotations

from strategy119 import _atr, _bars
from strategy188 import DEFAULT_CFG as _S188_DEFAULT_CFG
from strategy188 import detect_s188


DEFAULT_CFG = dict(_S188_DEFAULT_CFG)
DEFAULT_CFG.update({
    "STRUCTURE_LOOKBACK": 18,
    "SWEEP_BUFFER_ATR": 0.02,
    "TP_RR": 16.90,
    "BE_RR": 0.52,
})


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s189(rates, tf, dt_bkk, cfg):
    """Require an expected-shortfall reclaim to sweep rolling structure."""
    merged = dict(DEFAULT_CFG)
    if cfg:
        merged.update(cfg)
    result = detect_s188(rates, tf, dt_bkk, merged)
    signal = result.get("signal")
    if signal not in ("BUY", "SELL"):
        return result
    try:
        lookback = max(4, int(merged["STRUCTURE_LOOKBACK"]))
        period = max(1, int(merged["ATR_PERIOD"]))
        bars = _bars(rates)
        atr = _atr(bars[:-2], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid structural-sweep input: {exc}")
    if len(bars) < lookback + 3 or atr <= 0.0:
        return _wait("Not enough structure data or ATR is zero")
    exhaustion = bars[-2]
    structure = bars[-lookback - 2:-2]
    buffer = atr * float(merged["SWEEP_BUFFER_ATR"])
    if signal == "BUY":
        if exhaustion["low"] >= min(bar["low"] for bar in structure) - buffer:
            return _wait("Lower expected-shortfall breach did not sweep structure")
    elif exhaustion["high"] <= max(bar["high"] for bar in structure) + buffer:
        return _wait("Upper expected-shortfall breach did not sweep structure")
    rr = max(7.0, float(merged["TP_RR"]))
    result = dict(result)
    result["pattern"] = f"S189 {signal} ES Structural Sweep {rr:g}R"
    result["reason"] = f"Expected-shortfall tail plus structural liquidity sweep; {result['reason']}"
    return result
