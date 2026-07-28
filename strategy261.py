# -*- coding: utf-8 -*-
"""S261 - Bayesian return-sign persistence structural breakout, 10R.

The detector estimates a first-order Markov transition matrix for closed-bar
return signs with a symmetric beta prior.  It trades an efficient structural
break only when the posterior probability of the current direction persisting
is high, separating directional order-flow regimes from alternating noise.
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
    "MARKOV_LOOKBACK": 64,
    "BETA_PRIOR": 2.00,
    "PERSISTENCE_MIN": 0.62,
    "MIN_DIRECTION_TRANSITIONS": 8,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def _bar_close(bar):
    if isinstance(bar, dict):
        return float(bar["close"])
    try:
        return float(bar["close"])
    except (IndexError, KeyError, TypeError, ValueError):
        return float(bar.close)


def _posterior_persistence(signs, direction, prior):
    same = 0
    opposite = 0
    for previous, current in zip(signs, signs[1:]):
        if previous != direction:
            continue
        if current == direction:
            same += 1
        else:
            opposite += 1
    total = same + opposite
    probability = (same + prior) / (total + 2.0 * prior)
    return probability, total


def detect_s261(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a breakout aligned with Bayesian return-sign persistence."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(16, int(c["MARKOV_LOOKBACK"]))
        prior = float(c["BETA_PRIOR"])
        threshold = float(c["PERSISTENCE_MIN"])
        min_transitions = max(1, int(c["MIN_DIRECTION_TRANSITIONS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if prior <= 0.0 or not 0.5 <= threshold < 1.0:
        return _wait("Invalid Markov posterior parameters")
    if rates is None or len(rates) < lookback + 3 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")

    try:
        closes = [_bar_close(bar) for bar in rates[-lookback - 2:]]
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
    signs = [1 if value > 0.0 else -1 if value < 0.0 else 0 for value in returns]
    signs = [value for value in signs if value]
    if len(signs) < lookback // 2:
        return _wait("Too few non-zero returns for Markov state")
    direction = signs[-1]
    probability, transitions = _posterior_persistence(
        signs[-lookback - 1:-1], direction, prior
    )
    if transitions < min_transitions:
        return _wait(f"Too few same-state transitions ({transitions})")
    if probability < threshold:
        return _wait(f"Return-sign persistence is weak ({probability:.2f})")

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    breakout = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    expected = "BUY" if direction > 0 else "SELL"
    if breakout.get("signal") != expected:
        return _wait("Markov state lacks aligned structural break")
    breakout["pattern"] = (
        f"S261 {expected} Bayesian-Markov Persistence "
        f"{float(c['TP_RR']):g}R"
    )
    breakout["reason"] = (
        f"Efficient break with posterior sign persistence "
        f"p={probability:.2f} from {transitions} transitions"
    )
    return breakout
