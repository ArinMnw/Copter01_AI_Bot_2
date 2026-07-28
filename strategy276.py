# -*- coding: utf-8 -*-
"""S276 - Robust tick-volume lead/lag structural breakout, 10R.

Tick-volume surprises are standardized with a rolling median and MAD.  S276
estimates the correlation between each surprise and the following closed-bar
return, requires a significant lead relationship, then trades an efficient
structural break only when its direction matches the return implied by the
current completed bar's volume surprise.
"""

from __future__ import annotations

import math
import statistics

from strategy197 import _wait
from strategy232 import DEFAULT_CFG as S232_DEFAULT_CFG
from strategy232 import detect_s232


DEFAULT_CFG = {
    **S232_DEFAULT_CFG,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "LEAD_LOOKBACK": 96,
    "LEAD_CORRELATION_MIN": 0.20,
    "LEAD_T_MIN": 2.00,
    "VOLUME_SURPRISE_MIN": 1.00,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def _value(bar, key):
    if isinstance(bar, dict):
        return float(bar[key])
    try:
        return float(bar[key])
    except (IndexError, KeyError, TypeError, ValueError):
        return float(getattr(bar, key))


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


def detect_s276(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a breakout aligned with significant volume-led return pressure."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(32, int(c["LEAD_LOOKBACK"]))
        correlation_min = float(c["LEAD_CORRELATION_MIN"])
        t_min = float(c["LEAD_T_MIN"])
        surprise_min = float(c["VOLUME_SURPRISE_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not 0.0 <= correlation_min < 1.0 or t_min < 0.0 or surprise_min < 0.0:
        return _wait("Invalid lead/lag parameters")
    if rates is None or len(rates) < lookback + 4 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")

    try:
        bars = rates[-lookback - 3:]
        closes = [_value(bar, "close") for bar in bars]
        volumes = [max(0.0, _value(bar, "tick_volume")) for bar in bars]
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
    baseline_volumes = volumes[:-1]
    median_volume = statistics.median(baseline_volumes)
    mad = statistics.median(
        abs(value - median_volume) for value in baseline_volumes
    )
    if mad <= 0.0:
        return _wait("Tick-volume MAD is zero")
    scale = 1.4826 * mad
    surprises = [(value - median_volume) / scale for value in volumes]

    # surprise[t] predicts close-to-close return[t+1]; omit current unknown target.
    lead_values = surprises[1:-1]
    future_returns = returns[1:]
    sample_size = min(len(lead_values), len(future_returns))
    lead_values = lead_values[-lookback:][:sample_size]
    future_returns = future_returns[-lookback:][:sample_size]
    rho = _correlation(lead_values, future_returns)
    if rho is None or abs(rho) < correlation_min:
        return _wait(f"Volume lead correlation is weak ({rho})")
    if abs(rho) >= 1.0:
        t_statistic = math.inf
    else:
        t_statistic = abs(rho) * math.sqrt(
            (sample_size - 2.0) / max(1e-12, 1.0 - rho * rho)
        )
    if t_statistic < t_min:
        return _wait(f"Volume lead is insignificant (t={t_statistic:.2f})")
    current_surprise = surprises[-1]
    if abs(current_surprise) < surprise_min:
        return _wait(f"Current volume surprise is weak ({current_surprise:.2f})")
    expected = "BUY" if rho * current_surprise > 0.0 else "SELL"

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    breakout = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if breakout.get("signal") != expected:
        return _wait("Volume-led forecast lacks aligned structural break")
    rr = max(7.0, float(c["TP_RR"]))
    breakout["pattern"] = (
        f"S276 {expected} Volume Lead-Lag Breakout {rr:g}R"
    )
    breakout["reason"] = (
        f"Efficient break aligned with volume lead rho={rho:.2f}, "
        f"t={t_statistic:.2f}, surprise={current_surprise:.2f}"
    )
    return breakout
