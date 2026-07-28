# -*- coding: utf-8 -*-
"""S272 - ARCH-LM volatility-cluster structural breakout, 10R.

The lag-one Engle ARCH-LM statistic is estimated from squared demeaned returns.
S272 requires statistically clustered conditional variance and a fresh return-
variance impulse before following an efficient structural break.  This targets
self-exciting volatility continuation rather than level or residual reversion.
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
    "ARCH_LOOKBACK": 96,
    "ARCH_LM_MIN": 3.84,
    "VARIANCE_IMPULSE_MIN": 2.50,
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


def _correlation(left, right):
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    numerator = sum(
        (x_value - mean_left) * (y_value - mean_right)
        for x_value, y_value in zip(left, right)
    )
    left_ss = sum((value - mean_left) ** 2 for value in left)
    right_ss = sum((value - mean_right) ** 2 for value in right)
    denominator = math.sqrt(left_ss * right_ss)
    return numerator / denominator if denominator > 0.0 else None


def detect_s272(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a fresh variance impulse in a significant ARCH regime."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(32, int(c["ARCH_LOOKBACK"]))
        lm_min = float(c["ARCH_LM_MIN"])
        impulse_min = float(c["VARIANCE_IMPULSE_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if lm_min < 0.0 or impulse_min <= 1.0:
        return _wait("Invalid ARCH parameters")
    if rates is None or len(rates) < lookback + 4 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")

    try:
        closes = [_close(bar) for bar in rates[-lookback - 3:]]
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
    history = returns[-lookback - 2:-1]
    mean_return = sum(history) / len(history)
    squared = [(value - mean_return) ** 2 for value in history]
    rho = _correlation(squared[:-1], squared[1:])
    if rho is None:
        return _wait("ARCH correlation is unavailable")
    lm_statistic = len(squared[1:]) * rho * rho
    if lm_statistic < lm_min:
        return _wait(f"ARCH-LM is insignificant ({lm_statistic:.2f})")

    baseline_variance = sum(squared[:-1]) / len(squared[:-1])
    if baseline_variance <= 0.0:
        return _wait("Return variance is zero")
    previous_ratio = (returns[-2] - mean_return) ** 2 / baseline_variance
    current_ratio = (returns[-1] - mean_return) ** 2 / baseline_variance
    if previous_ratio >= impulse_min or current_ratio < impulse_min:
        return _wait(
            f"No fresh variance impulse "
            f"(prev={previous_ratio:.2f}, current={current_ratio:.2f})"
        )
    expected = "BUY" if returns[-1] > mean_return else "SELL"

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    breakout = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if breakout.get("signal") != expected:
        return _wait("Variance impulse lacks aligned structural break")
    rr = max(7.0, float(c["TP_RR"]))
    breakout["pattern"] = (
        f"S272 {expected} ARCH-Cluster Breakout {rr:g}R"
    )
    breakout["reason"] = (
        f"Fresh variance impulse {current_ratio:.2f}x in ARCH regime "
        f"(LM={lm_statistic:.2f}, rho={rho:.2f})"
    )
    return breakout
