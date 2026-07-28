# -*- coding: utf-8 -*-
"""S233 - US-liquidity-window RS compression breakout, 27.2R.

S232 showed that session-agnostic Rogers-Satchell compression breaks overtrade.
The 17:00-19:00 BKK scheduled US-liquidity overlap was the coherent profitable
sub-regime, unlike isolated profitable clock hours.  S233 keeps the exact S232
trigger and risk model but allows it only inside that causal clock window.
"""

from __future__ import annotations

from strategy197 import _wait
from strategy232 import DEFAULT_CFG as S232_DEFAULT_CFG, detect_s232


DEFAULT_CFG = dict(S232_DEFAULT_CFG)
DEFAULT_CFG.update({
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 19,
    "TP_RR": 27.20,
    "BE_RR": 0.85,
})


def detect_s233(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade RS compression breaks only during scheduled US liquidity."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if dt_bkk is None:
        return _wait("dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    result = detect_s232(rates, tf, dt_bkk, c)
    if result.get("signal") in ("BUY", "SELL"):
        signal = result["signal"]
        rr = max(7.0, float(c["TP_RR"]))
        result["pattern"] = f"S233 {signal} US RS Compression Break {rr:g}R"
        result["reason"] = (
            f"US-liquidity-window {result['reason'][0].lower()}"
            f"{result['reason'][1:]}"
        )
    return result
