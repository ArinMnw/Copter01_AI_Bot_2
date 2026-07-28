# -*- coding: utf-8 -*-
"""S245 - CLV-pressure breakout with tick-volume surprise, 10R.

S240's persistent positive auction pressure is retained, but the breakout bar
must carry materially more tick volume than the prior 24-bar median.  This
tests whether fresh participation confirms that the range release is tradable.
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
    "BREAK_VOLUME_RATIO_MIN": 1.50,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def detect_s245(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Buy a positive-CLV range break confirmed by volume surprise."""
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
    if volume_ratio < float(c["BREAK_VOLUME_RATIO_MIN"]):
        return _wait(f"Breakout volume is ordinary ({volume_ratio:.2f}x)")

    signal = detect_s240(rates, tf, dt_bkk, c, **kwargs)
    if signal.get("signal") != "BUY":
        return signal
    rr = max(7.0, float(c["TP_RR"]))
    signal = dict(signal)
    signal["pattern"] = f"S245 BUY CLV-Pressure Volume-Surprise Break {rr:g}R"
    signal["reason"] = (
        f"Positive-CLV upside break with tick-volume surprise "
        f"({volume_ratio:.2f}x median)"
    )
    return signal
