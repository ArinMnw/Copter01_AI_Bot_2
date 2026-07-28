# -*- coding: utf-8 -*-
"""S236 - US-window dual-estimator compression breakout, 10R.

This is the complement to S235: both Rogers-Satchell and Parkinson short-term
variance must be compressed versus their shared long baseline.  Agreement
selects a broad quiet regime rather than the estimator-disagreement regime.
"""

from __future__ import annotations

from strategy119 import _bars
from strategy197 import _wait
from strategy232 import DEFAULT_CFG as S232_DEFAULT_CFG
from strategy232 import detect_s232
from strategy234 import _parkinson_variance


DEFAULT_CFG = {
    **S232_DEFAULT_CFG,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 19,
    "PARKINSON_COMPRESSION_MAX": 0.65,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def detect_s236(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a US range break after both volatility estimators compress."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
        short_window = max(4, int(c["RS_SHORT_WINDOW"]))
        long_window = max(short_window + 4, int(c["RS_LONG_WINDOW"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < long_window + 3 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        history = bars[-long_window - 1:-1]
        values = [_parkinson_variance(bar) for bar in history]
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    long_mean = sum(values) / len(values)
    if long_mean <= 0.0:
        return _wait("Long Parkinson variance is zero")
    parkinson_ratio = (
        sum(values[-short_window:]) / short_window
    ) / long_mean
    if parkinson_ratio > float(c["PARKINSON_COMPRESSION_MAX"]):
        return _wait(
            f"Parkinson volatility is not compressed "
            f"(ratio={parkinson_ratio:.2f})"
        )

    signal = detect_s232(rates, tf, dt_bkk, c, **kwargs)
    if signal.get("signal") not in ("BUY", "SELL"):
        return signal
    side = signal["signal"]
    rr = max(7.0, float(c["TP_RR"]))
    signal = dict(signal)
    signal["pattern"] = f"S236 {side} Dual Compression Break {rr:g}R"
    signal["reason"] = (
        f"US-window efficient break with RS/Parkinson compression agreement "
        f"(Parkinson={parkinson_ratio:.2f})"
    )
    return signal
