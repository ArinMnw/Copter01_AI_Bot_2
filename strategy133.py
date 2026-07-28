# -*- coding: utf-8 -*-
"""S133 — High Range-Consumption Asia Inventory Carry."""

from __future__ import annotations

from datetime import datetime
from statistics import median

from strategy116 import _normalise_rates
from strategy128 import DEFAULT_CFG as S128_DEFAULT_CFG
from strategy128 import detect_s128


DEFAULT_CFG = {
    **S128_DEFAULT_CFG,
    "RANGE_HISTORY_DAYS": 5,
    "MIN_COMPLETED_DAYS": 3,
    "DAILY_MIN_BARS": 180,
    "ASIA_TO_MEDIAN_RANGE_MIN": 0.70,
    "MEDIAN_RANGE_MIN": 0.01,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s133(rates, tf, dt_bkk, cfg):
    """Return S128 carry only after high Asia range consumption."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    if rates is None or dt_bkk is None or dt_bkk.tzinfo is None:
        return _wait("Rates or timezone-aware dt_bkk missing")
    base_cfg = {key: value for key, value in c.items() if key in S128_DEFAULT_CFG}
    result = detect_s128(rates, tf, dt_bkk, base_cfg)
    if result.get("signal") not in ("BUY", "SELL"):
        return result
    try:
        bars = _normalise_rates(rates)
        day_start = dt_bkk.replace(hour=0, minute=0, second=0, microsecond=0)
        asia_start = day_start.replace(hour=int(c["ASIA_START_HOUR"]))
        asia_end = day_start.replace(hour=int(c["ASIA_END_HOUR"]))
        history_days = max(1, int(c["RANGE_HISTORY_DAYS"]))
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid input: {exc}")

    daily = {}
    day_ts = int(day_start.timestamp())
    for bar in bars:
        if bar["time"] >= day_ts:
            continue
        key = datetime.fromtimestamp(bar["time"], tz=dt_bkk.tzinfo).date()
        daily.setdefault(key, []).append(bar)
    ranges = []
    for key in sorted(daily, reverse=True):
        group = daily[key]
        if len(group) < int(c["DAILY_MIN_BARS"]):
            continue
        ranges.append(max(bar["high"] for bar in group) - min(bar["low"] for bar in group))
        if len(ranges) >= history_days:
            break
    if len(ranges) < int(c["MIN_COMPLETED_DAYS"]):
        return _wait("Not enough completed daily ranges")

    asia = [bar for bar in bars
            if int(asia_start.timestamp()) <= bar["time"] < int(asia_end.timestamp())]
    if len(asia) < int(c["ASIA_MIN_BARS"]):
        return _wait("Asia session is incomplete")
    reference = median(ranges)
    if reference < float(c["MEDIAN_RANGE_MIN"]):
        return _wait("Median daily range is zero or invalid")
    asia_range = max(bar["high"] for bar in asia) - min(bar["low"] for bar in asia)
    consumption = asia_range / reference
    if consumption <= float(c["ASIA_TO_MEDIAN_RANGE_MIN"]):
        return _wait(f"Asia range consumption is not high ({consumption:.0%})")

    result = dict(result)
    result["pattern"] = f"S133 {result['signal']} High-Consumption Asia Carry"
    result["reason"] = (f"{result.get('reason', '')}; Asia/median daily range="
                        f"{consumption:.0%} across {len(ranges)} days")
    return result
