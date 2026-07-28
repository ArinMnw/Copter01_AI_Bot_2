# -*- coding: utf-8 -*-
"""S247 - CLV-pressure normal-participation breakout, optimized 42R.

After high-volume S245 failed and low-volume S246 produced no sample, S247
tests the remaining pre-declared partition: breakout tick volume between 0.85
and 1.50 times its prior 24-bar median.
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
    "BREAK_VOLUME_RATIO_MIN": 0.85,
    "BREAK_VOLUME_RATIO_MAX": 1.50,
    "TP_RR": 42.00,
    "BE_RR": 0.10,
}


def detect_s247(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Buy a positive-CLV break with normal tick-volume participation."""
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
    if not (
        float(c["BREAK_VOLUME_RATIO_MIN"])
        <= volume_ratio
        <= float(c["BREAK_VOLUME_RATIO_MAX"])
    ):
        return _wait(f"Breakout volume is outside normal regime ({volume_ratio:.2f}x)")

    signal = detect_s240(rates, tf, dt_bkk, c, **kwargs)
    if signal.get("signal") != "BUY":
        return signal
    rr = max(7.0, float(c["TP_RR"]))
    signal = dict(signal)
    signal["pattern"] = f"S247 BUY CLV Normal-Participation Break {rr:g}R"
    signal["reason"] = (
        f"Positive-CLV upside break with normal tick-volume participation "
        f"({volume_ratio:.2f}x median)"
    )
    return signal
