# -*- coding: utf-8 -*-
"""S263 - Bayesian ordinal-pattern structural breakout, 10R.

Three-bar closing-price ranks form an ordinal state that is invariant to the
absolute price scale.  The detector estimates, using only earlier occurrences,
the posterior probability that each state is followed by an up or down close.
It trades only an efficient structural break aligned with a sufficiently
reliable nonlinear path-state posterior.
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
    "ORDINAL_LOOKBACK": 96,
    "BETA_PRIOR": 2.00,
    "POSTERIOR_MIN": 0.65,
    "MIN_PATTERN_SAMPLES": 5,
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


def _ordinal_pattern(values):
    """Return stable ranks; index breaks ties without using future data."""
    ordered = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0] * len(values)
    for rank, index in enumerate(ordered):
        ranks[index] = rank
    return tuple(ranks)


def detect_s263(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a structural break predicted by a Bayesian ordinal state."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(24, int(c["ORDINAL_LOOKBACK"]))
        prior = float(c["BETA_PRIOR"])
        posterior_min = float(c["POSTERIOR_MIN"])
        min_samples = max(2, int(c["MIN_PATTERN_SAMPLES"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if prior <= 0.0 or not 0.5 < posterior_min < 1.0:
        return _wait("Invalid ordinal posterior parameters")
    if rates is None or len(rates) < lookback + 5 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")

    try:
        closes = [_close(bar) for bar in rates[-lookback - 4:]]
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        AttributeError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    current_pattern = _ordinal_pattern(closes[-3:])
    up = 0
    down = 0
    # The final completed event has no known next bar inside the detector.
    for endpoint in range(2, len(closes) - 1):
        pattern = _ordinal_pattern(closes[endpoint - 2:endpoint + 1])
        if pattern != current_pattern:
            continue
        next_change = closes[endpoint + 1] - closes[endpoint]
        if next_change > 0.0:
            up += 1
        elif next_change < 0.0:
            down += 1
    samples = up + down
    if samples < min_samples:
        return _wait(f"Ordinal state has too few samples ({samples})")
    probability_up = (up + prior) / (samples + 2.0 * prior)
    if probability_up >= posterior_min:
        expected = "BUY"
        confidence = probability_up
    elif 1.0 - probability_up >= posterior_min:
        expected = "SELL"
        confidence = 1.0 - probability_up
    else:
        return _wait(f"Ordinal posterior is weak (p_up={probability_up:.2f})")

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    breakout = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if breakout.get("signal") != expected:
        return _wait("Ordinal forecast lacks aligned structural break")
    rr = max(7.0, float(c["TP_RR"]))
    breakout["pattern"] = (
        f"S263 {expected} Bayesian Ordinal Breakout {rr:g}R"
    )
    breakout["reason"] = (
        f"Efficient break aligned with ordinal state {current_pattern}; "
        f"posterior={confidence:.2f}, n={samples}"
    )
    return breakout
