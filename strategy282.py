# -*- coding: utf-8 -*-
"""S282 - Low-turning-point persistent structural breakout, 10R.

For an independent continuous sequence, the expected number of local turning
points is 2(n-2)/3 with known variance.  S282 follows an efficient structural
break only when the closed-price path has significantly fewer turning points
than randomness predicts, indicating smooth directional persistence.
"""

from __future__ import annotations

import math

from strategy197 import _wait
from strategy232 import DEFAULT_CFG as S232_DEFAULT_CFG
from strategy232 import detect_s232


DEFAULT_CFG = {
    **S232_DEFAULT_CFG,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "TURNING_LOOKBACK": 64,
    "TURNING_Z_MAX": -1.50,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def _close(bar):
    if isinstance(bar, dict):
        return float(bar["close"])
    try:
        return float(bar["close"])
    except (IndexError, KeyError, TypeError, ValueError):
        return float(bar.close)


def _turning_zscore(values):
    size = len(values)
    if size < 4:
        return None, 0
    turns = sum(
        1
        for left, middle, right in zip(values, values[1:], values[2:])
        if (middle > left and middle > right)
        or (middle < left and middle < right)
    )
    expected = 2.0 * (size - 2.0) / 3.0
    variance = (16.0 * size - 29.0) / 90.0
    if variance <= 0.0:
        return None, turns
    return (turns - expected) / math.sqrt(variance), turns


def detect_s282(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a structural break in a low-turning persistent path."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(16, int(c["TURNING_LOOKBACK"]))
        z_max = float(c["TURNING_Z_MAX"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < lookback + 3 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        closes = [_close(bar) for bar in rates[-lookback - 1:-1]]
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        AttributeError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    zscore, turns = _turning_zscore(closes)
    if zscore is None:
        return _wait("Turning-point statistic is unavailable")
    if zscore > z_max:
        return _wait(f"Path is not persistently smooth (z={zscore:.2f})")

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    breakout = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if breakout.get("signal") not in ("BUY", "SELL"):
        return breakout
    rr = max(7.0, float(c["TP_RR"]))
    breakout["pattern"] = (
        f"S282 {breakout['signal']} Low-Turning Breakout {rr:g}R"
    )
    breakout["reason"] = (
        f"Efficient break with fewer turns than random "
        f"(z={zscore:.2f}, turns={turns})"
    )
    return breakout
