# -*- coding: utf-8 -*-
"""S131 — Asia Inventory Carry with Daily-Range Capacity.

Keep S128's cross-session carry setup, but accept it only when the completed
Asia range has not consumed too much of the previous BKK calendar day's range.
The capacity gate is direction-neutral and uses only already closed bars.
"""

from __future__ import annotations

from strategy116 import _normalise_rates
from strategy128 import DEFAULT_CFG as S128_DEFAULT_CFG
from strategy128 import detect_s128


DEFAULT_CFG = {
    **S128_DEFAULT_CFG,
    "PREVIOUS_DAY_MIN_BARS": 180,
    "ASIA_TO_PREVIOUS_DAY_RANGE_MAX": 0.70,
    "PREVIOUS_DAY_RANGE_MIN": 0.01,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s131(rates, tf, dt_bkk, cfg):
    """Return S128 carry only when meaningful daily range remains available."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    if rates is None or dt_bkk is None or dt_bkk.tzinfo is None:
        return _wait("Rates or timezone-aware dt_bkk missing")
    try:
        bars = _normalise_rates(rates)
        day_start = dt_bkk.replace(hour=0, minute=0, second=0, microsecond=0)
        previous_start = day_start.fromtimestamp(
            day_start.timestamp() - 86400, tz=dt_bkk.tzinfo
        )
        asia_start = day_start.replace(hour=int(c["ASIA_START_HOUR"]))
        asia_end = day_start.replace(hour=int(c["ASIA_END_HOUR"]))
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid input: {exc}")

    previous = [bar for bar in bars
                if int(previous_start.timestamp()) <= bar["time"] < int(day_start.timestamp())]
    asia = [bar for bar in bars
            if int(asia_start.timestamp()) <= bar["time"] < int(asia_end.timestamp())]
    if len(previous) < int(c["PREVIOUS_DAY_MIN_BARS"]):
        return _wait("Previous BKK day is incomplete")
    if len(asia) < int(c["ASIA_MIN_BARS"]):
        return _wait("Asia session is incomplete")

    previous_range = max(bar["high"] for bar in previous) - min(bar["low"] for bar in previous)
    asia_range = max(bar["high"] for bar in asia) - min(bar["low"] for bar in asia)
    if previous_range < float(c["PREVIOUS_DAY_RANGE_MIN"]):
        return _wait("Previous-day range is zero or invalid")
    capacity_ratio = asia_range / previous_range
    if capacity_ratio > float(c["ASIA_TO_PREVIOUS_DAY_RANGE_MAX"]):
        return _wait(f"Asia consumed too much daily range ({capacity_ratio:.0%})")

    base_cfg = {key: value for key, value in c.items() if key in S128_DEFAULT_CFG}
    result = detect_s128(rates, tf, dt_bkk, base_cfg)
    if result.get("signal") not in ("BUY", "SELL"):
        return result
    result = dict(result)
    result["pattern"] = f"S131 {result['signal']} Asia Carry Capacity"
    result["reason"] = (f"{result.get('reason', '')}; Asia/prior-day range="
                        f"{capacity_ratio:.0%}, remaining capacity confirmed")
    return result
