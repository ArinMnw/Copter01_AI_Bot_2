# -*- coding: utf-8 -*-
"""S285 - Mann-Kendall no-trend failed-sweep reclaim, 10R.

A failed structural sweep is a mean-reversion event. S285 permits that event
only when the closed-price path has no significant Mann-Kendall monotonic
tendency, avoiding fades against an established directional regime.
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
    "MK_Z_MAX_ABS": 0.75,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def detect_s285(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a failed sweep only in a Mann-Kendall no-trend regime."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(16, int(c["MK_LOOKBACK"]))
        z_max = max(0.0, float(c["MK_Z_MAX_ABS"]))
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
    if abs(zscore) > z_max:
        return _wait(f"Path has a monotonic trend (z={zscore:.2f})")

    reclaim_cfg = dict(c)
    reclaim_cfg["TURNING_Z_MIN"] = -math.inf
    reclaim = detect_s283(rates, tf, dt_bkk, reclaim_cfg, **kwargs)
    if reclaim.get("signal") not in ("BUY", "SELL"):
        return reclaim
    rr = max(7.0, float(c["TP_RR"]))
    reclaim["pattern"] = (
        f"S285 {reclaim['signal']} MK No-Trend Reclaim {rr:g}R"
    )
    reclaim["reason"] = (
        f"Failed sweep in Mann-Kendall no-trend regime (z={zscore:.2f})"
    )
    return reclaim
