# -*- coding: utf-8 -*-
"""S286 - Optimized Mann-Kendall trend sweep-reclaim, SELL-only 27R.

In a significant monotonic trend, a sweep against the trend followed by a
close back inside local structure can expose a stop-run pullback. S286 enters
only when the reclaim direction agrees with the Mann-Kendall trend.
"""

from __future__ import annotations

import math

from strategy197 import _wait
from strategy282 import _close
from strategy283 import DEFAULT_CFG as S283_DEFAULT_CFG
from strategy283 import detect_s283
from strategy284 import _mann_kendall_z


DEFAULT_CFG = {
    **S283_DEFAULT_CFG,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "MK_LOOKBACK": 64,
    "MK_Z_MIN_ABS": 2.50,
    "SWEEP_LOOKBACK": 14,
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    "TP_RR": 27.00,
    "BE_RR": 1.59,
}


def detect_s286(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a sweep-reclaim that resumes a significant MK trend."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(16, int(c["MK_LOOKBACK"]))
        z_min = max(0.0, float(c["MK_Z_MIN_ABS"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < lookback + 3 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
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
        return _wait(f"No significant monotonic trend (z={zscore:.2f})")

    reclaim_cfg = dict(c)
    reclaim_cfg["TURNING_Z_MIN"] = -math.inf
    reclaim = detect_s283(rates, tf, dt_bkk, reclaim_cfg, **kwargs)
    if reclaim.get("signal") not in ("BUY", "SELL"):
        return reclaim
    if reclaim["signal"] == "BUY" and zscore <= 0.0:
        return _wait(f"BUY reclaim conflicts with falling MK trend (z={zscore:.2f})")
    if reclaim["signal"] == "SELL" and zscore >= 0.0:
        return _wait(f"SELL reclaim conflicts with rising MK trend (z={zscore:.2f})")
    rr = max(7.0, float(c["TP_RR"]))
    reclaim["pattern"] = (
        f"S286 {reclaim['signal']} MK Trend Sweep-Reclaim {rr:g}R"
    )
    reclaim["reason"] = (
        f"Counter-trend liquidity sweep reclaimed with MK trend "
        f"(z={zscore:.2f})"
    )
    return reclaim
