# -*- coding: utf-8 -*-
"""S348 - Acceptance-edge failed-breakout reclaim fade.

S348 is the falsification complement of S347.  It first identifies migrated
acceptance near a baseline range edge, then fades only a closed candle that
sweeps the recent edge and reclaims back inside the acceptance threshold.

All shelf inputs precede the reclaim candle.  Entry is next-open market, SL is
beyond the closed sweep extreme plus ATR, and TP is at least 7R.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy347 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 64,
    "RECENT_BARS": 20,
    "RECENT_EDGE_DISTANCE_MIN": 0.18,
    "ACCEPTANCE_SHIFT_MIN": 0.12,
    "RECENT_COORDINATE_IQR_MAX": 0.35,
    "EDGE_ACCEPTANCE_RATE_MIN": 0.55,
    "EDGE_ACCEPTANCE_THRESHOLD": 0.65,
    "MIGRATION_EFFICIENCY_MIN": 0.12,
    "SWEEP_ATR_MIN": 0.02,
    "RECLAIM_BODY_ATR_MIN": 0.35,
    "RECLAIM_RANGE_ATR_MIN": 0.80,
    "REJECTION_WICK_FRACTION_MIN": 0.20,
    "RECLAIM_CLOSE_FRACTION": 0.60,
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


def detect_s348(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a swept and reclaimed migrated acceptance edge."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        edge_distance_min = float(c["RECENT_EDGE_DISTANCE_MIN"])
        shift_min = float(c["ACCEPTANCE_SHIFT_MIN"])
        iqr_max = float(c["RECENT_COORDINATE_IQR_MAX"])
        acceptance_rate_min = float(c["EDGE_ACCEPTANCE_RATE_MIN"])
        edge_threshold = float(c["EDGE_ACCEPTANCE_THRESHOLD"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (
            edge_distance_min,
            shift_min,
            iqr_max,
            acceptance_rate_min,
            edge_threshold,
        )
    ):
        return _wait("Invalid config: acceptance-reclaim gates invalid")
    if edge_threshold <= 0.5:
        return _wait("Invalid config: edge threshold must exceed 0.5")

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
        baseline_low = min(bar["low"] for bar in baseline)
        baseline_high = max(bar["high"] for bar in baseline)
        baseline_range = baseline_high - baseline_low
        if baseline_range <= 0.0:
            return _wait("Baseline range is zero")
        baseline_coordinates = [
            (bar["close"] - baseline_low) / baseline_range
            for bar in baseline
        ]
        recent_coordinates = [
            (bar["close"] - baseline_low) / baseline_range
            for bar in recent
        ]
        baseline_median = statistics.median(baseline_coordinates)
        recent_median = statistics.median(recent_coordinates)
        recent_iqr = (
            _quantile(recent_coordinates, 0.75)
            - _quantile(recent_coordinates, 0.25)
        )
        atr = _atr(bars[:-1], period)
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        ZeroDivisionError,
        AttributeError,
        statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    migration_side = 1 if recent_median > 0.5 else -1
    edge_distance = migration_side * (recent_median - 0.5)
    acceptance_shift = migration_side * (
        recent_median - baseline_median
    )
    if migration_side > 0:
        acceptance_rate = sum(
            coordinate >= edge_threshold
            for coordinate in recent_coordinates
        ) / len(recent_coordinates)
    else:
        lower_threshold = 1.0 - edge_threshold
        acceptance_rate = sum(
            coordinate <= lower_threshold
            for coordinate in recent_coordinates
        ) / len(recent_coordinates)
    if (
        edge_distance < edge_distance_min
        or acceptance_shift < shift_min
        or recent_iqr > iqr_max
        or acceptance_rate < acceptance_rate_min
    ):
        return _wait(
            f"No migrated acceptance edge "
            f"(median={baseline_median:.3f}->{recent_median:.3f}, "
            f"shift={acceptance_shift:.3f}, IQR={recent_iqr:.3f}, "
            f"rate={acceptance_rate:.3f})"
        )

    net_move = recent[-1]["close"] - recent[0]["close"]
    travelled = sum(
        abs(recent[index]["close"] - recent[index - 1]["close"])
        for index in range(1, len(recent))
    )
    if travelled <= 0.0 or net_move * migration_side <= 0.0:
        return _wait("Recent path opposes acceptance migration")
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["MIGRATION_EFFICIENCY_MIN"]):
        return _wait(f"Acceptance migration is inefficient ({efficiency:.3f})")

    recent_edge = (
        max(bar["high"] for bar in recent)
        if migration_side > 0
        else min(bar["low"] for bar in recent)
    )
    sweep = migration_side * (
        (event["high"] if migration_side > 0 else event["low"])
        - recent_edge
    )
    if sweep < atr * float(c["SWEEP_ATR_MIN"]):
        return _wait("Reclaim candle did not sweep the recent edge")

    reclaim_coordinate = (event["close"] - baseline_low) / baseline_range
    if migration_side > 0 and reclaim_coordinate >= edge_threshold:
        return _wait("Upper-edge sweep has not reclaimed inside")
    if (
        migration_side < 0
        and reclaim_coordinate <= 1.0 - edge_threshold
    ):
        return _wait("Lower-edge sweep has not reclaimed inside")

    side = -migration_side
    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Reclaim body does not confirm the fade")
    if abs(body) < atr * float(c["RECLAIM_BODY_ATR_MIN"]):
        return _wait("Reclaim body is too small versus ATR")
    if candle_range < atr * float(c["RECLAIM_RANGE_ATR_MIN"]):
        return _wait("Reclaim range is too small versus ATR")
    rejection_wick = (
        event["high"] - max(event["open"], event["close"])
        if side < 0
        else min(event["open"], event["close"]) - event["low"]
    )
    if (
        rejection_wick / candle_range
        < float(c["REJECTION_WICK_FRACTION_MIN"])
    ):
        return _wait("Reclaim lacks rejection wick")
    close_fraction = (
        (event["close"] - event["low"]) / candle_range
        if side > 0
        else (event["high"] - event["close"]) / candle_range
    )
    if close_fraction < float(c["RECLAIM_CLOSE_FRACTION"]):
        return _wait("Reclaim lacks directional close control")

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
        return _wait(f"Reclaim risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Reclaim risk too large versus price")

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
        "pattern": f"S348 {signal} Acceptance Reclaim {rr:g}R",
        "reason": (
            f"edge median {baseline_median:.4f}->{recent_median:.4f}, "
            f"sweep={sweep / atr:.3f}ATR, "
            f"reclaim={reclaim_coordinate:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
