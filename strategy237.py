# -*- coding: utf-8 -*-
"""S237 - US-window Garman-Klass volatility-compression breakout, 10R.

Garman-Klass combines the high-low range with an open-close drift correction.
This controlled estimator ablation keeps the S233 session, breakout geometry,
and structural risk model unchanged.
"""

from __future__ import annotations

import math

from strategy119 import _bars
from strategy197 import _wait
from strategy232 import DEFAULT_CFG as S232_DEFAULT_CFG
from strategy232 import detect_s232


DEFAULT_CFG = {
    **S232_DEFAULT_CFG,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 19,
    "GK_SHORT_WINDOW": 12,
    "GK_LONG_WINDOW": 72,
    "GK_COMPRESSION_MAX": 0.65,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def _garman_klass_variance(bar):
    open_price = float(bar["open"])
    high = float(bar["high"])
    low = float(bar["low"])
    close = float(bar["close"])
    if min(open_price, high, low, close) <= 0.0 or high < low:
        return 0.0
    log_range = math.log(high / low)
    log_close_open = math.log(close / open_price)
    value = (
        0.5 * log_range * log_range
        - (2.0 * math.log(2.0) - 1.0) * log_close_open * log_close_open
    )
    return max(0.0, value)


def detect_s237(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a US-window efficient break after GK variance compresses."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
        short_window = max(4, int(c["GK_SHORT_WINDOW"]))
        long_window = max(short_window + 4, int(c["GK_LONG_WINDOW"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < long_window + 3 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        history = bars[-long_window - 1:-1]
        values = [_garman_klass_variance(bar) for bar in history]
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    long_mean = sum(values) / len(values)
    if long_mean <= 0.0:
        return _wait("Long Garman-Klass variance is zero")
    compression_ratio = (
        sum(values[-short_window:]) / short_window
    ) / long_mean
    if compression_ratio > float(c["GK_COMPRESSION_MAX"]):
        return _wait(
            f"Garman-Klass volatility is not compressed "
            f"(ratio={compression_ratio:.2f})"
        )

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    signal = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if signal.get("signal") not in ("BUY", "SELL"):
        return signal
    side = signal["signal"]
    rr = max(7.0, float(c["TP_RR"]))
    signal = dict(signal)
    signal["pattern"] = f"S237 {side} US Garman-Klass Compression Break {rr:g}R"
    signal["reason"] = (
        f"US-window efficient break after Garman-Klass compression "
        f"(short/long={compression_ratio:.2f})"
    )
    return signal
