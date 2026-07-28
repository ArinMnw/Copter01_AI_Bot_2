# -*- coding: utf-8 -*-
"""S246 - CLV-pressure liquidity-vacuum breakout, 10R.

This is the controlled complement to failed S245.  Persistent positive auction
pressure remains required, while the breakout occurs on below-median tick
volume, testing whether low opposing liquidity lets price travel farther.
"""

from __future__ import annotations

from statistics import median

from strategy119 import _bars
from strategy197 import _wait
from strategy240 import DEFAULT_CFG as S240_DEFAULT_CFG
from strategy240 import detect_s240


DEFAULT_CFG = {
    **S240_DEFAULT_CFG,
    "VOLUME_BASELINE_WINDOW": 24,
    "BREAK_VOLUME_RATIO_MAX": 0.85,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def detect_s246(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Buy a positive-CLV range break occurring in a volume vacuum."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        volume_window = max(8, int(c["VOLUME_BASELINE_WINDOW"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < volume_window + 3 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        baseline = median(
            float(bar["tick_volume"])
            for bar in bars[-volume_window - 1:-1]
        )
        breakout_volume = float(bars[-1]["tick_volume"])
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if baseline <= 0.0:
        return _wait("Tick-volume baseline is zero")
    volume_ratio = breakout_volume / baseline
    if volume_ratio > float(c["BREAK_VOLUME_RATIO_MAX"]):
        return _wait(f"Breakout is not in a volume vacuum ({volume_ratio:.2f}x)")

    signal = detect_s240(rates, tf, dt_bkk, c, **kwargs)
    if signal.get("signal") != "BUY":
        return signal
    rr = max(7.0, float(c["TP_RR"]))
    signal = dict(signal)
    signal["pattern"] = f"S246 BUY CLV-Pressure Liquidity-Vacuum Break {rr:g}R"
    signal["reason"] = (
        f"Positive-CLV upside break in a tick-volume vacuum "
        f"({volume_ratio:.2f}x median)"
    )
    return signal
