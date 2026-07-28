# -*- coding: utf-8 -*-
"""S123 — S121 Reversal-Candle Risk Compression.

Keep S121's asymmetric upside-exhaustion signal unchanged, but test whether a
stop above the closed reversal candle plus ATR buffer is superior to S120's
wide stop above the full expansion window.
"""

from __future__ import annotations

import math

import strategy121
from strategy119 import _atr, _bars


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SL_REVERSAL_BUFFER_ATR": 0.20,
    "MAX_RISK_ATR": 2.50,
    "TP_RR": 1.80,
    "S121_CFG": {},
}


def detect_s123(rates, tf, dt_bkk, cfg):
    """Compress S121 risk behind the latest fully closed reversal candle."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    source = strategy121.detect_s121(rates, tf, dt_bkk, dict(c.get("S121_CFG") or {}))
    if source.get("signal") != "SELL":
        return {"signal": "WAIT", "reason": f"S121 source: {source.get('reason', 'WAIT')}"}
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], int(c["ATR_PERIOD"]))
        entry = float(source["entry"])
        sl = bars[-1]["high"] + atr * float(c["SL_REVERSAL_BUFFER_ATR"])
        risk = sl - entry
        if atr <= 0.0 or risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
            return {"signal": "WAIT", "reason": "Compressed risk is invalid"}
        rr = max(1.5, float(c["TP_RR"]))
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return {"signal": "WAIT", "reason": "Invalid S123 input or cfg"}
    entry_r, sl_r = round(entry, 2), round(sl, 2)
    rounded_risk = sl_r - entry_r
    if rounded_risk <= 0.0:
        return {"signal": "WAIT", "reason": "Risk vanished after rounding"}
    tp = math.floor((entry_r - rr * rounded_risk + 1e-12) * 100.0) / 100.0
    return {
        "signal": "SELL", "entry": entry_r, "sl": sl_r, "tp": tp,
        "order_type": "limit", "pattern": "S123 SELL RV Compressed Stop",
        "reason": (f"S121 signal with reversal-candle stop {rounded_risk / atr:.2f}ATR; "
                   f"{source['reason']}"),
        "be_rr": source.get("be_rr", 1.0),
        "cancel_bars": source.get("cancel_bars", 3),
    }
