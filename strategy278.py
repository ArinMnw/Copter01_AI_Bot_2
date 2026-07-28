# -*- coding: utf-8 -*-
"""S278 - Directional Ulcer-asymmetry structural breakout, 10R.

The downside Ulcer index is the RMS percentage drawdown from the running peak;
its upside analogue is the RMS drawup from the running trough.  Their ratio
captures path-dependent inventory stress.  S278 follows an efficient structural
break only when its direction agrees with a strong historical stress asymmetry.
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
    "ULCER_LOOKBACK": 64,
    "ULCER_RATIO_MIN": 1.50,
    "ULCER_FLOOR": 0.0001,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
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


def _directional_ulcer(closes):
    running_peak = closes[0]
    running_trough = closes[0]
    downside_squared = 0.0
    upside_squared = 0.0
    for close in closes:
        running_peak = max(running_peak, close)
        running_trough = min(running_trough, close)
        downside = (running_peak - close) / running_peak
        upside = (close - running_trough) / running_trough
        downside_squared += downside * downside
        upside_squared += upside * upside
    size = len(closes)
    return (
        math.sqrt(downside_squared / size),
        math.sqrt(upside_squared / size),
    )


def detect_s278(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a breakout aligned with path-dependent Ulcer asymmetry."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(16, int(c["ULCER_LOOKBACK"]))
        ratio_min = float(c["ULCER_RATIO_MIN"])
        floor = float(c["ULCER_FLOOR"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if ratio_min <= 1.0 or floor <= 0.0:
        return _wait("Invalid Ulcer parameters")
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
    if min(closes) <= 0.0:
        return _wait("Close price must be positive")
    downside, upside = _directional_ulcer(closes)
    if downside < floor and upside < floor:
        return _wait("Directional Ulcer stress is negligible")
    if downside / max(upside, floor) >= ratio_min:
        expected = "SELL"
        ratio = downside / max(upside, floor)
    elif upside / max(downside, floor) >= ratio_min:
        expected = "BUY"
        ratio = upside / max(downside, floor)
    else:
        return _wait(
            f"Directional Ulcer stress is balanced "
            f"(down={downside:.4f}, up={upside:.4f})"
        )
    if expected == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled by direction-survival filter")
    if expected == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled by direction-survival filter")

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    breakout = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if breakout.get("signal") != expected:
        return _wait("Ulcer asymmetry lacks aligned structural break")
    rr = max(7.0, float(c["TP_RR"]))
    breakout["pattern"] = (
        f"S278 {expected} Directional-Ulcer Breakout {rr:g}R"
    )
    breakout["reason"] = (
        f"Efficient break aligned with path stress ratio={ratio:.2f}, "
        f"down={downside:.4f}, up={upside:.4f}"
    )
    return breakout
