# -*- coding: utf-8 -*-
"""S343 - Auction range-overlap fragmentation release.

S343 measures normalized overlap between consecutive closed candle ranges.
Falling recent overlap and more non-overlapping transitions indicate that
price acceptance is migrating instead of repeatedly auctioning the same area.

All overlap and path inputs precede the release candle.  Entry is next-open
market, SL is beyond the closed release extreme plus ATR, and TP is at least
7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 64,
    "RECENT_BARS": 20,
    "RECENT_MEAN_OVERLAP_MAX": 0.45,
    "MEAN_OVERLAP_DROP_MIN": 0.10,
    "RECENT_NON_OVERLAP_RATE_MIN": 0.15,
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
    "ALLOW_SELL": True,
    "TP_RR": 8.0,
    "BE_RR": 0.08,
    "CANCEL_BARS": 3,
}


def _overlap_profile(bars):
    if len(bars) < 8:
        return None
    coefficients = []
    non_overlaps = 0
    for index in range(1, len(bars)):
        previous_low = float(bars[index - 1]["low"])
        previous_high = float(bars[index - 1]["high"])
        current_low = float(bars[index]["low"])
        current_high = float(bars[index]["high"])
        values = (previous_low, previous_high, current_low, current_high)
        if not all(math.isfinite(value) for value in values):
            return None
        previous_range = previous_high - previous_low
        current_range = current_high - current_low
        if previous_range <= 0.0 or current_range <= 0.0:
            return None
        overlap = max(
            0.0,
            min(previous_high, current_high)
            - max(previous_low, current_low),
        )
        coefficient = overlap / min(previous_range, current_range)
        coefficients.append(max(0.0, min(1.0, coefficient)))
        non_overlaps += int(overlap <= 0.0)
    return (
        sum(coefficients) / len(coefficients),
        non_overlaps / len(coefficients),
    )


def detect_s343(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after consecutive auction ranges fragment."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        recent_overlap_max = float(c["RECENT_MEAN_OVERLAP_MAX"])
        overlap_drop_min = float(c["MEAN_OVERLAP_DROP_MIN"])
        non_overlap_min = float(c["RECENT_NON_OVERLAP_RATE_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (
            recent_overlap_max,
            overlap_drop_min,
            non_overlap_min,
        )
    ):
        return _wait("Invalid config: auction-overlap gates are invalid")

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
        baseline_profile = _overlap_profile(baseline)
        recent_profile = _overlap_profile(recent)
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
    if baseline_profile is None or recent_profile is None:
        return _wait("Auction-overlap profile is unavailable")

    baseline_overlap, _ = baseline_profile
    recent_overlap, recent_non_overlap = recent_profile
    overlap_drop = baseline_overlap - recent_overlap
    if (
        recent_overlap > recent_overlap_max
        or overlap_drop < overlap_drop_min
        or recent_non_overlap < non_overlap_min
    ):
        return _wait(
            f"No auction-overlap fragmentation "
            f"({baseline_overlap:.3f}->{recent_overlap:.3f}, "
            f"drop={overlap_drop:.3f}, nonoverlap={recent_non_overlap:.3f})"
        )

    net_move = recent[-1]["close"] - recent[0]["close"]
    travelled = sum(
        abs(recent[index]["close"] - recent[index - 1]["close"])
        for index in range(1, len(recent))
    )
    if travelled <= 0.0:
        return _wait("Recent path has no movement")
    side = 1 if net_move > 0.0 else -1
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes auction-migration direction")
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
        "pattern": f"S343 {signal} Auction Fragmentation {rr:g}R",
        "reason": (
            f"range overlap {baseline_overlap:.4f}->{recent_overlap:.4f}, "
            f"drop={overlap_drop:.4f}, nonoverlap={recent_non_overlap:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
