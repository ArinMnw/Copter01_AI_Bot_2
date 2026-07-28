# -*- coding: utf-8 -*-
"""S270 - Stationary OU residual structural continuation, 10R."""

from __future__ import annotations

import math
import statistics

from strategy197 import _wait
from strategy232 import detect_s232
from strategy269 import DEFAULT_CFG as S269_DEFAULT_CFG
from strategy269 import _ar1_phi, _linear_residuals


DEFAULT_CFG = {
    **S269_DEFAULT_CFG,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
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


def detect_s270(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a fresh OU residual excursion with an aligned range break."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(32, int(c["OU_LOOKBACK"]))
        threshold = float(c["RESIDUAL_Z_MIN"])
        half_life_min = float(c["HALF_LIFE_MIN"])
        half_life_max = float(c["HALF_LIFE_MAX"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < lookback + 3 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        closes = [_close(bar) for bar in rates[-lookback:]]
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        AttributeError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    fitted = _linear_residuals(closes)
    if fitted is None:
        return _wait("Linear detrending is degenerate")
    residuals, trend_slope = fitted
    phi = _ar1_phi(residuals[:-1])
    if phi is None or not 0.0 < phi < 1.0:
        return _wait(f"Residual is not stationary OU (phi={phi})")
    half_life = -math.log(2.0) / math.log(phi)
    if not half_life_min <= half_life <= half_life_max:
        return _wait(f"OU half-life outside range ({half_life:.1f} bars)")
    scale = statistics.pstdev(residuals[:-1])
    if scale <= 0.0:
        return _wait("OU residual scale is zero")
    previous_zscore = residuals[-2] / scale
    current_zscore = residuals[-1] / scale
    if abs(previous_zscore) >= threshold or abs(current_zscore) < threshold:
        return _wait(
            f"No fresh OU residual crossing "
            f"(prev={previous_zscore:.2f}, current={current_zscore:.2f})"
        )
    expected = "BUY" if current_zscore > 0.0 else "SELL"
    if expected == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled by direction-survival filter")
    if expected == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled by direction-survival filter")

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    breakout = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if breakout.get("signal") != expected:
        return _wait("OU excursion lacks aligned structural break")
    rr = max(7.0, float(c["TP_RR"]))
    breakout["pattern"] = (
        f"S270 {expected} OU Residual Continuation {rr:g}R"
    )
    breakout["reason"] = (
        f"Efficient break with fresh OU residual z={current_zscore:.2f}, "
        f"half-life={half_life:.1f}, trend={trend_slope:.3f}"
    )
    return breakout
