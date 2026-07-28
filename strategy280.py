# -*- coding: utf-8 -*-
"""S280 - Lempel-Ziv low-complexity structural breakout, 10R.

The Lempel-Ziv phrase count measures algorithmic novelty in the binary sequence
of closed-bar return signs.  S280 follows an efficient structural breakout only
when normalized sign complexity is low, targeting repeatable directional path
structure rather than a conventional trend indicator.
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
    "LZ_LOOKBACK": 96,
    "LZ_COMPLEXITY_MAX": 0.78,
    "MIN_DIRECTION_BALANCE": 0.20,
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


def _lz_complexity(sequence):
    """Return a simple exhaustive-history LZ76 phrase count."""
    size = len(sequence)
    index = 0
    phrases = 0
    while index < size:
        length = 1
        history = sequence[:index]
        while (
            index + length <= size
            and sequence[index:index + length] in history
        ):
            length += 1
        phrases += 1
        index += length
    return phrases


def detect_s280(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a structural break in a low-complexity return-sign regime."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(32, int(c["LZ_LOOKBACK"]))
        complexity_max = float(c["LZ_COMPLEXITY_MAX"])
        balance_min = float(c["MIN_DIRECTION_BALANCE"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if complexity_max <= 0.0 or not 0.0 <= balance_min <= 0.5:
        return _wait("Invalid Lempel-Ziv parameters")
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
    signs = []
    for previous, current in zip(closes, closes[1:]):
        if current > previous:
            signs.append("1")
        elif current < previous:
            signs.append("0")
    if len(signs) < lookback * 0.75:
        return _wait("Too few non-zero returns for Lempel-Ziv state")
    positive_fraction = signs.count("1") / len(signs)
    if min(positive_fraction, 1.0 - positive_fraction) < balance_min:
        return _wait("Sign sequence is directionally degenerate")
    sequence = "".join(signs[-lookback:])
    phrase_count = _lz_complexity(sequence)
    normalized = phrase_count * math.log2(len(sequence)) / len(sequence)
    if normalized > complexity_max:
        return _wait(f"Return-sign complexity is high ({normalized:.2f})")

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    breakout = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if breakout.get("signal") not in ("BUY", "SELL"):
        return breakout
    rr = max(7.0, float(c["TP_RR"]))
    breakout["pattern"] = (
        f"S280 {breakout['signal']} LZ-Structured Breakout {rr:g}R"
    )
    breakout["reason"] = (
        f"Efficient break in low-complexity sign path "
        f"(LZ={normalized:.2f}, phrases={phrase_count})"
    )
    return breakout
