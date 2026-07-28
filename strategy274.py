# -*- coding: utf-8 -*-
"""S274 - Multi-scale DFA-persistence structural breakout, 10R.

Detrended fluctuation analysis integrates demeaned returns, removes a local
linear trend inside non-overlapping segments, and estimates the log-log scaling
of residual fluctuation.  S274 follows an efficient structural breakout only
when the DFA exponent indicates persistent long-memory dynamics.
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
    "DFA_LOOKBACK": 128,
    "DFA_SCALES": (8, 16, 32, 64),
    "DFA_ALPHA_MIN": 0.62,
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


def _segment_rms(values):
    size = len(values)
    mean_x = (size - 1.0) / 2.0
    mean_y = sum(values) / size
    denominator = sum((index - mean_x) ** 2 for index in range(size))
    if denominator <= 0.0:
        return 0.0
    slope = sum(
        (index - mean_x) * (value - mean_y)
        for index, value in enumerate(values)
    ) / denominator
    intercept = mean_y - slope * mean_x
    squared = sum(
        (value - (intercept + slope * index)) ** 2
        for index, value in enumerate(values)
    )
    return math.sqrt(squared / size)


def _dfa_alpha(returns, scales):
    mean_return = sum(returns) / len(returns)
    profile = []
    running = 0.0
    for value in returns:
        running += value - mean_return
        profile.append(running)
    points = []
    for scale in scales:
        segments = len(profile) // scale
        if segments < 2:
            continue
        squared_fluctuation = 0.0
        used = 0
        for segment_index in range(segments):
            start = segment_index * scale
            rms = _segment_rms(profile[start:start + scale])
            if rms > 0.0:
                squared_fluctuation += rms * rms
                used += 1
        if used:
            fluctuation = math.sqrt(squared_fluctuation / used)
            if fluctuation > 0.0:
                points.append((math.log(scale), math.log(fluctuation)))
    if len(points) < 3:
        return None
    mean_x = sum(point[0] for point in points) / len(points)
    mean_y = sum(point[1] for point in points) / len(points)
    denominator = sum((point[0] - mean_x) ** 2 for point in points)
    if denominator <= 0.0:
        return None
    return sum(
        (x_value - mean_x) * (y_value - mean_y)
        for x_value, y_value in points
    ) / denominator


def detect_s274(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a structural break in a DFA-persistent regime."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(64, int(c["DFA_LOOKBACK"]))
        scales = tuple(sorted({max(4, int(value)) for value in c["DFA_SCALES"]}))
        alpha_min = float(c["DFA_ALPHA_MIN"])
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
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        ZeroDivisionError,
        AttributeError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    alpha = _dfa_alpha(returns, scales)
    if alpha is None:
        return _wait("DFA exponent is unavailable")
    if alpha < alpha_min:
        return _wait(f"DFA regime is not persistent (alpha={alpha:.2f})")

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    breakout = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if breakout.get("signal") not in ("BUY", "SELL"):
        return breakout
    rr = max(7.0, float(c["TP_RR"]))
    breakout["pattern"] = (
        f"S274 {breakout['signal']} DFA-Persistence Breakout {rr:g}R"
    )
    breakout["reason"] = (
        f"Efficient break in multi-scale DFA regime (alpha={alpha:.2f})"
    )
    return breakout
