# -*- coding: utf-8 -*-
"""S248 - Multi-scale Hurst-persistence range breakout, 10R.

Rescaled-range statistics estimate whether recent returns are persistent across
8, 16, and 32-bar horizons.  A high cross-scale Hurst slope must precede an
efficient structural range break during the US liquidity window.
"""

from __future__ import annotations

import math
from statistics import pstdev

from strategy119 import _bars
from strategy197 import _wait
from strategy232 import DEFAULT_CFG as S232_DEFAULT_CFG
from strategy232 import detect_s232


DEFAULT_CFG = {
    **S232_DEFAULT_CFG,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "HURST_WINDOW": 64,
    "HURST_SCALES": (8, 16, 32),
    "HURST_MIN": 0.62,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _rescaled_range(values):
    if len(values) < 4:
        return None
    center = _mean(values)
    cumulative = total = 0.0
    path = []
    for value in values:
        total += value - center
        path.append(total)
    scale = pstdev(values)
    if scale <= 0.0:
        return None
    cumulative = max(path) - min(path)
    return cumulative / scale if cumulative > 0.0 else None


def _hurst_rs(returns, scales):
    points = []
    for scale in scales:
        estimates = []
        for start in range(0, len(returns) - scale + 1, scale):
            estimate = _rescaled_range(returns[start:start + scale])
            if estimate is not None and estimate > 0.0:
                estimates.append(estimate)
        if estimates:
            points.append((math.log(float(scale)), math.log(_mean(estimates))))
    if len(points) < 2:
        return None
    mean_x = _mean([point[0] for point in points])
    mean_y = _mean([point[1] for point in points])
    denominator = sum((point[0] - mean_x) ** 2 for point in points)
    if denominator <= 0.0:
        return None
    return sum(
        (point[0] - mean_x) * (point[1] - mean_y)
        for point in points
    ) / denominator


def detect_s248(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a US range break when multi-scale returns are persistent."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
        window = max(32, int(c["HURST_WINDOW"]))
        scales = tuple(sorted({max(4, int(value)) for value in c["HURST_SCALES"]}))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < window + 3 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        closes = [float(bar["close"]) for bar in bars[-window - 2:-1]]
        if min(closes) <= 0.0:
            return _wait("Non-positive close")
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
        hurst = _hurst_rs(returns, scales)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if hurst is None:
        return _wait("Hurst estimate is unavailable")
    if hurst < float(c["HURST_MIN"]):
        return _wait(f"Return path is not persistent (H={hurst:.2f})")

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    signal = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if signal.get("signal") not in ("BUY", "SELL"):
        return signal
    side = signal["signal"]
    rr = max(7.0, float(c["TP_RR"]))
    signal = dict(signal)
    signal["pattern"] = f"S248 {side} Hurst-Persistence Break {rr:g}R"
    signal["reason"] = (
        f"US range break in multi-scale persistent return regime "
        f"(H={hurst:.2f})"
    )
    return signal
