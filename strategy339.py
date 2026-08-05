# -*- coding: utf-8 -*-
"""S339 - Directional record-statistics price-discovery release.

S339 counts sequential record highs and lows of closed prices.  Frequent new
records on one side are a distribution-free signature of sustained price
discovery.  The recent directional record rate is compared with equal-sized,
disjoint baseline blocks so sample length cannot create a mechanical bias.

Every record and path input precedes the release candle.  Entry is next-open
market, SL is beyond the closed release extreme plus ATR, and TP is at least
7R.
"""

from __future__ import annotations

import math
from statistics import median

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 60,
    "RECENT_BARS": 20,
    "RECENT_RECORD_RATE_MIN": 0.25,
    "RECORD_RATE_JUMP_MIN": 0.10,
    "RECORD_RATE_ASYMMETRY_MIN": 0.15,
    "MIN_DIRECTIONAL_RECORDS": 5,
    "PATH_EFFICIENCY_MIN": 0.22,
    "NET_MOVE_ATR_MIN": 0.55,
    "RELEASE_BODY_ATR_MIN": 0.72,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.80,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": False,
    "TP_RR": 8.0,
    "BE_RR": 0.08,
    "CANCEL_BARS": 3,
}


def _record_profile(bars):
    closes = [float(bar["close"]) for bar in bars]
    if (
        len(closes) < 4
        or any(not math.isfinite(value) for value in closes)
    ):
        return None
    running_high = closes[0]
    running_low = closes[0]
    high_records = 0
    low_records = 0
    for value in closes[1:]:
        if value > running_high:
            high_records += 1
            running_high = value
        if value < running_low:
            low_records += 1
            running_low = value
    denominator = len(closes) - 1
    return (
        high_records / denominator,
        low_records / denominator,
        high_records,
        low_records,
    )


def detect_s339(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after directional record creation accelerates."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        recent_rate_min = float(c["RECENT_RECORD_RATE_MIN"])
        jump_min = float(c["RECORD_RATE_JUMP_MIN"])
        asymmetry_min = float(c["RECORD_RATE_ASYMMETRY_MIN"])
        minimum_records = max(1, int(c["MIN_DIRECTIONAL_RECORDS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (recent_rate_min, jump_min, asymmetry_min)
    ):
        return _wait("Invalid config: record-statistic gates are invalid")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline must cover a recent-sized block")

    required = max(period + 5, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        recent_profile = _record_profile(recent)
        blocks = [
            baseline[index:index + recent_count]
            for index in range(0, baseline_count - recent_count + 1, recent_count)
        ]
        baseline_profiles = [_record_profile(block) for block in blocks]
        atr = _atr(bars[:-1], period)
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        ZeroDivisionError,
        AttributeError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    if (
        recent_profile is None
        or len(baseline_profiles) < 2
        or any(profile is None for profile in baseline_profiles)
    ):
        return _wait("Record-statistic profile is unavailable")

    recent_high, recent_low, high_count, low_count = recent_profile
    side = 1 if recent_high > recent_low else -1
    recent_side = recent_high if side > 0 else recent_low
    recent_other = recent_low if side > 0 else recent_high
    record_count = high_count if side > 0 else low_count
    baseline_side = median([
        profile[0] if side > 0 else profile[1]
        for profile in baseline_profiles
    ])
    rate_jump = recent_side - baseline_side
    asymmetry = recent_side - recent_other
    if (
        recent_side < recent_rate_min
        or rate_jump < jump_min
        or asymmetry < asymmetry_min
        or record_count < minimum_records
    ):
        return _wait(
            f"No directional record acceleration "
            f"({baseline_side:.3f}->{recent_side:.3f}, "
            f"jump={rate_jump:.3f}, asym={asymmetry:.3f}, "
            f"records={record_count})"
        )

    net_move = recent[-1]["close"] - recent[0]["close"]
    travelled = sum(
        abs(recent[index]["close"] - recent[index - 1]["close"])
        for index in range(1, len(recent))
    )
    if travelled <= 0.0:
        return _wait("Recent path has no movement")
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move is too small")
    if net_move * side <= 0.0:
        return _wait("Recent path opposes record direction")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes record direction")
    if abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if candle_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    close_fraction = (
        (event["close"] - event["low"]) / candle_range
        if side > 0
        else (event["high"] - event["close"]) / candle_range
    )
    if close_fraction < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Release lacks directional close control")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(event["close"], 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor(
            (event["low"] - sl_buffer + 1e-12) * 100.0
        ) / 100.0
    else:
        sl = math.ceil(
            (event["high"] + sl_buffer - 1e-12) * 100.0
        ) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Release risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Release risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    tp = (
        math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
        if side > 0
        else math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    )
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S339 {signal} Record Discovery {rr:g}R",
        "reason": (
            f"record rate {baseline_side:.4f}->{recent_side:.4f}, "
            f"jump={rate_jump:.4f}, asymmetry={asymmetry:.4f}, "
            f"records={record_count}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
