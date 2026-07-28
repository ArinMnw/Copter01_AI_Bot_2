# -*- coding: utf-8 -*-
"""S244 - CLV-pressure acceleration breakout, 10R.

The long-side edge in S240 may come from fresh auction-pressure transitions
rather than persistently elevated pressure.  S244 requires six-bar
volume-weighted CLV to accelerate materially above a 24-bar baseline before an
efficient upside range break.
"""

from __future__ import annotations

from strategy119 import _bars
from strategy197 import _wait
from strategy240 import DEFAULT_CFG as S240_DEFAULT_CFG
from strategy240 import detect_s240


DEFAULT_CFG = {
    **S240_DEFAULT_CFG,
    "PRESSURE_SHORT_WINDOW": 6,
    "PRESSURE_LONG_WINDOW": 24,
    "MIN_SHORT_CLV_PRESSURE": 0.25,
    "MAX_LONG_CLV_PRESSURE": 0.12,
    "MIN_PRESSURE_ACCELERATION": 0.20,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def _weighted_clv(bars):
    weighted = total_volume = 0.0
    for bar in bars:
        bar_range = float(bar["high"]) - float(bar["low"])
        volume = max(0.0, float(bar["tick_volume"]))
        if bar_range > 0.0 and volume > 0.0:
            clv = (
                (float(bar["close"]) - float(bar["low"]))
                - (float(bar["high"]) - float(bar["close"]))
            ) / bar_range
            weighted += volume * clv
            total_volume += volume
    return weighted / total_volume if total_volume > 0.0 else None


def detect_s244(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Buy a range break after short-horizon CLV pressure accelerates."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        short_window = max(3, int(c["PRESSURE_SHORT_WINDOW"]))
        long_window = max(short_window + 4, int(c["PRESSURE_LONG_WINDOW"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < long_window + 3 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        history = bars[-long_window - 1:-1]
        short_pressure = _weighted_clv(history[-short_window:])
        long_pressure = _weighted_clv(history)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if short_pressure is None or long_pressure is None:
        return _wait("Tick volume is unavailable")
    acceleration = short_pressure - long_pressure
    if short_pressure < float(c["MIN_SHORT_CLV_PRESSURE"]):
        return _wait(f"Short CLV pressure is weak ({short_pressure:.2f})")
    if long_pressure > float(c["MAX_LONG_CLV_PRESSURE"]):
        return _wait(f"Long CLV pressure is already elevated ({long_pressure:.2f})")
    if acceleration < float(c["MIN_PRESSURE_ACCELERATION"]):
        return _wait(f"CLV pressure did not accelerate ({acceleration:.2f})")

    breakout_cfg = dict(c)
    breakout_cfg["EFFORT_WINDOW"] = short_window
    breakout_cfg["MIN_SIGNED_EFFORT"] = float(c["MIN_SHORT_CLV_PRESSURE"])
    breakout_cfg["TP_RR"] = float(c["TP_RR"])
    breakout_cfg["BE_RR"] = float(c["BE_RR"])
    signal = detect_s240(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if signal.get("signal") != "BUY":
        return signal
    rr = max(7.0, float(c["TP_RR"]))
    signal = dict(signal)
    signal["pattern"] = f"S244 BUY CLV-Pressure Acceleration Break {rr:g}R"
    signal["reason"] = (
        f"Upside break after CLV pressure acceleration "
        f"(short={short_pressure:.2f}, long={long_pressure:.2f}, "
        f"delta={acceleration:.2f})"
    )
    return signal
