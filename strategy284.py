# -*- coding: utf-8 -*-
"""S284 - Mann-Kendall monotonic-trend structural breakout, 10R.

The Mann-Kendall statistic is distribution-free and tests whether a closed
price sequence has a significant monotonic tendency. S284 accepts an efficient
structural breakout only when its direction agrees with that tendency.
"""

from __future__ import annotations

import math
from collections import Counter

from strategy197 import _wait
from strategy232 import DEFAULT_CFG as S232_DEFAULT_CFG
from strategy232 import detect_s232
from strategy282 import _close


DEFAULT_CFG = {
    **S232_DEFAULT_CFG,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "MK_LOOKBACK": 64,
    "MK_Z_MIN_ABS": 2.00,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def _mann_kendall_z(values):
    """Return tie-corrected Mann-Kendall z with continuity correction."""
    size = len(values)
    if size < 4:
        return None
    ordered = {value: rank + 1 for rank, value in enumerate(sorted(set(values)))}
    tree = [0] * (len(ordered) + 1)

    def prefix(index):
        total = 0
        while index > 0:
            total += tree[index]
            index -= index & -index
        return total

    def add(index):
        while index < len(tree):
            tree[index] += 1
            index += index & -index

    score = 0
    seen = 0
    for value in values:
        rank = ordered[value]
        less = prefix(rank - 1)
        less_or_equal = prefix(rank)
        score += less - (seen - less_or_equal)
        add(rank)
        seen += 1
    tie_term = sum(
        count * (count - 1) * (2 * count + 5)
        for count in Counter(values).values()
        if count > 1
    )
    variance = (
        size * (size - 1) * (2 * size + 5) - tie_term
    ) / 18.0
    if variance <= 0.0:
        return None
    if score > 0:
        return (score - 1.0) / math.sqrt(variance)
    if score < 0:
        return (score + 1.0) / math.sqrt(variance)
    return 0.0


def detect_s284(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a structural break confirmed by a monotonic MK trend."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(16, int(c["MK_LOOKBACK"]))
        z_min = max(0.0, float(c["MK_Z_MIN_ABS"]))
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
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        AttributeError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    zscore = _mann_kendall_z(closes)
    if zscore is None:
        return _wait("Mann-Kendall statistic is unavailable")
    if abs(zscore) < z_min:
        return _wait(f"No significant monotonic path (z={zscore:.2f})")

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    breakout = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if breakout.get("signal") not in ("BUY", "SELL"):
        return breakout
    if breakout["signal"] == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled by direction-survival filter")
    if breakout["signal"] == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled by direction-survival filter")
    if breakout["signal"] == "BUY" and zscore <= 0.0:
        return _wait(f"BUY break conflicts with falling MK path (z={zscore:.2f})")
    if breakout["signal"] == "SELL" and zscore >= 0.0:
        return _wait(f"SELL break conflicts with rising MK path (z={zscore:.2f})")
    rr = max(7.0, float(c["TP_RR"]))
    breakout["pattern"] = (
        f"S284 {breakout['signal']} Mann-Kendall Breakout {rr:g}R"
    )
    breakout["reason"] = (
        f"Efficient structural break agrees with monotonic MK trend "
        f"(z={zscore:.2f})"
    )
    return breakout
