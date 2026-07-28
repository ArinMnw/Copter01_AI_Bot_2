# -*- coding: utf-8 -*-
"""S265 - Lagged volume-return mutual-information breakout, 10R.

Tick volume is discretized relative to its rolling median.  S265 measures the
mutual information between that liquidity-participation state and the sign of
the following closed-bar return, then uses a beta posterior to infer the next
direction from the current volume state.  A trade requires an aligned efficient
structural break, avoiding a generic volume threshold.
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
    "MI_LOOKBACK": 96,
    "MUTUAL_INFORMATION_MIN": 0.015,
    "BETA_PRIOR": 2.00,
    "POSTERIOR_MIN": 0.62,
    "MIN_STATE_SAMPLES": 12,
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


def _mutual_information(pairs):
    if not pairs:
        return 0.0
    total = float(len(pairs))
    joint = {(x, y): 0 for x in (0, 1) for y in (-1, 1)}
    count_x = {0: 0, 1: 0}
    count_y = {-1: 0, 1: 0}
    for state, direction in pairs:
        joint[(state, direction)] += 1
        count_x[state] += 1
        count_y[direction] += 1
    value = 0.0
    for (state, direction), count in joint.items():
        if count <= 0:
            continue
        probability = count / total
        value += probability * math.log(
            probability / ((count_x[state] / total) * (count_y[direction] / total))
        )
    return value


def detect_s265(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a breakout aligned with a volume-conditioned return posterior."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(32, int(c["MI_LOOKBACK"]))
        mi_min = float(c["MUTUAL_INFORMATION_MIN"])
        prior = float(c["BETA_PRIOR"])
        posterior_min = float(c["POSTERIOR_MIN"])
        min_samples = max(4, int(c["MIN_STATE_SAMPLES"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if mi_min < 0.0 or prior <= 0.0 or not 0.5 < posterior_min < 1.0:
        return _wait("Invalid mutual-information parameters")
    if rates is None or len(rates) < lookback + 4 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")

    try:
        bars = rates[-lookback - 2:]
        closes = [_value(bar, "close") for bar in bars]
        volumes = [max(0.0, _value(bar, "tick_volume")) for bar in bars]
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        AttributeError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    median_volume = statistics.median(volumes[:-1])
    if median_volume <= 0.0:
        return _wait("Median tick volume is zero")

    pairs = []
    for index in range(len(bars) - 1):
        change = closes[index + 1] - closes[index]
        if change == 0.0:
            continue
        state = 1 if volumes[index] >= median_volume else 0
        pairs.append((state, 1 if change > 0.0 else -1))
    information = _mutual_information(pairs[:-1])
    if information < mi_min:
        return _wait(f"Lagged volume information is weak ({information:.3f})")

    current_state = 1 if volumes[-1] >= median_volume else 0
    relevant = [direction for state, direction in pairs[:-1] if state == current_state]
    if len(relevant) < min_samples:
        return _wait(f"Volume state has too few samples ({len(relevant)})")
    up = sum(1 for direction in relevant if direction > 0)
    probability_up = (up + prior) / (len(relevant) + 2.0 * prior)
    if probability_up >= posterior_min:
        expected = "BUY"
        confidence = probability_up
    elif 1.0 - probability_up >= posterior_min:
        expected = "SELL"
        confidence = 1.0 - probability_up
    else:
        return _wait(f"Volume-conditioned posterior is weak ({probability_up:.2f})")

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    breakout = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if breakout.get("signal") != expected:
        return _wait("Volume forecast lacks aligned structural break")
    rr = max(7.0, float(c["TP_RR"]))
    breakout["pattern"] = (
        f"S265 {expected} Volume-MI Breakout {rr:g}R"
    )
    breakout["reason"] = (
        f"Efficient break with volume-return MI={information:.3f}, "
        f"posterior={confidence:.2f}, n={len(relevant)}"
    )
    return breakout
