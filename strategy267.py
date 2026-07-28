# -*- coding: utf-8 -*-
"""S267 - Wald-Wolfowitz persistent-runs structural breakout, 10R.

The Wald-Wolfowitz statistic compares the observed number of positive/negative
return runs with the number expected under independent signs.  A significantly
negative statistic indicates unusually long directional runs.  S267 follows an
efficient structural break only inside that distribution-free persistence
regime.
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
    "RUNS_LOOKBACK": 64,
    "RUNS_Z_MAX": -1.20,
    "MIN_SIGN_COUNT": 12,
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


def _runs_zscore(signs):
    positive = sum(1 for sign in signs if sign > 0)
    negative = sum(1 for sign in signs if sign < 0)
    total = positive + negative
    if min(positive, negative) <= 0 or total < 2:
        return None, positive, negative
    runs = 1 + sum(
        1 for previous, current in zip(signs, signs[1:])
        if previous != current
    )
    expected = 1.0 + 2.0 * positive * negative / total
    variance = (
        2.0
        * positive
        * negative
        * (2.0 * positive * negative - total)
        / (total * total * (total - 1.0))
    )
    if variance <= 0.0:
        return None, positive, negative
    return (runs - expected) / math.sqrt(variance), positive, negative


def detect_s267(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a structural break in a statistically persistent runs regime."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(24, int(c["RUNS_LOOKBACK"]))
        z_max = float(c["RUNS_Z_MAX"])
        min_count = max(2, int(c["MIN_SIGN_COUNT"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < lookback + 3 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")

    try:
        closes = [_close(bar) for bar in rates[-lookback - 2:-1]]
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        AttributeError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    signs = []
    for previous, current in zip(closes, closes[1:]):
        if current > previous:
            signs.append(1)
        elif current < previous:
            signs.append(-1)
    zscore, positive, negative = _runs_zscore(signs[-lookback:])
    if zscore is None or min(positive, negative) < min_count:
        return _wait("Runs test lacks balanced sign sample")
    if zscore > z_max:
        return _wait(f"Return runs are not persistent (z={zscore:.2f})")

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    breakout = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if breakout.get("signal") not in ("BUY", "SELL"):
        return breakout
    rr = max(7.0, float(c["TP_RR"]))
    breakout["pattern"] = (
        f"S267 {breakout['signal']} Persistent-Runs Breakout {rr:g}R"
    )
    breakout["reason"] = (
        f"Efficient break in Wald-Wolfowitz persistent regime "
        f"(z={zscore:.2f}, +={positive}, -={negative})"
    )
    return breakout
