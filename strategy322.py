# -*- coding: utf-8 -*-
"""S322 - Distance-correlation volume coupling release.

Distance correlation detects arbitrary dependence between absolute returns
and tick volume, including nonlinear relationships that rank concordance can
miss.  S322 compares non-overlapping baseline and recent coupling, then follows
a strong closed release in the recent path direction.

Every statistic precedes the release candle.  Entry is market at the next bar
open, the stop is beyond the release extreme plus ATR, and TP is at least 7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 48,
    # Recent14/16/18 are profitable in every window.  Recent18 improves
    # H1/WF net and drawdown while retaining every current 2m winner.
    "RECENT_RETURNS": 18,
    # Cross-window winner floors are 0.5100 dCor and 0.2131 jump.  These
    # gates reduce noise while retaining 0.05 and 0.033 of margin.
    "RECENT_DCOR_MIN": 0.46,
    "DCOR_JUMP_MIN": 0.18,
    "PATH_EFFICIENCY_MIN": 0.22,
    "NET_MOVE_ATR_MIN": 0.55,
    "RELEASE_BODY_ATR_MIN": 0.75,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.80,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    # Weakest cross-window winner reaches about 10.97R; keep 0.27R margin.
    "TP_RR": 10.7,
    "BE_RR": 0.05,
    "CANCEL_BARS": 3,
}


def _distance_correlation(first, second):
    """Return biased distance correlation without materializing centered matrices."""
    if len(first) != len(second) or len(first) < 6:
        return None
    size = len(first)
    first_row_sums = [0.0] * size
    second_row_sums = [0.0] * size
    raw_product_sum = 0.0
    first_square_sum = 0.0
    second_square_sum = 0.0
    for row in range(size):
        first_value = first[row]
        second_value = second[row]
        for column in range(size):
            first_distance = abs(first_value - first[column])
            second_distance = abs(second_value - second[column])
            first_row_sums[row] += first_distance
            second_row_sums[row] += second_distance
            raw_product_sum += first_distance * second_distance
            first_square_sum += first_distance * first_distance
            second_square_sum += second_distance * second_distance
    first_total = sum(first_row_sums)
    second_total = sum(second_row_sums)
    correction_scale = float(size)
    centered_product_sum = (
        raw_product_sum
        - 2.0 * sum(
            first_row_sums[index] * second_row_sums[index]
            for index in range(size)
        ) / correction_scale
        + first_total * second_total / (correction_scale * correction_scale)
    )
    centered_first_square_sum = (
        first_square_sum
        - 2.0 * sum(value * value for value in first_row_sums)
        / correction_scale
        + first_total * first_total
        / (correction_scale * correction_scale)
    )
    centered_second_square_sum = (
        second_square_sum
        - 2.0 * sum(value * value for value in second_row_sums)
        / correction_scale
        + second_total * second_total
        / (correction_scale * correction_scale)
    )
    scale = float(size * size)
    covariance_squared = centered_product_sum / scale
    variance_first_squared = centered_first_square_sum / scale
    variance_second_squared = centered_second_square_sum / scale
    denominator = math.sqrt(
        variance_first_squared * variance_second_squared
    )
    if denominator <= 0.0:
        return None
    correlation_squared = max(0.0, covariance_squared / denominator)
    return math.sqrt(correlation_squared)


def _coupling(bars):
    magnitudes = []
    volumes = []
    for index in range(1, len(bars)):
        previous = bars[index - 1]["close"]
        current = bars[index]["close"]
        if previous <= 0.0 or current <= 0.0:
            return None
        magnitudes.append(abs(math.log(current / previous)))
        volumes.append(bars[index]["tick_volume"])
    return _distance_correlation(magnitudes, volumes)


def detect_s322(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after nonlinear volume-return coupling increases."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(8, int(c["BASELINE_RETURNS"]))
        recent_count = max(6, int(c["RECENT_RETURNS"]))
        recent_min = float(c["RECENT_DCOR_MIN"])
        jump_min = float(c["DCOR_JUMP_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (recent_min, jump_min)
    ):
        return _wait("Invalid config: distance-correlation gates must be finite")

    required = max(period + 5, baseline_count + recent_count + 3)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 2:-1]
        baseline = history[:baseline_count + 1]
        recent = history[baseline_count:]
        baseline_dcor = _coupling(baseline)
        recent_dcor = _coupling(recent)
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
    if baseline_dcor is None or recent_dcor is None:
        return _wait("Distance correlation is unavailable")
    coupling_jump = recent_dcor - baseline_dcor
    if recent_dcor < recent_min or coupling_jump < jump_min:
        return _wait(
            f"No nonlinear coupling shift ({recent_dcor:.3f}, "
            f"jump={coupling_jump:.3f})"
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
    side = 1 if net_move > 0.0 else -1

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes the coupling path")
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
        sl = math.floor((event["low"] - sl_buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + sl_buffer - 1e-12) * 100.0) / 100.0
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
        "pattern": f"S322 {signal} Distance-Correlation Release {rr:g}R",
        "reason": (
            f"distance correlation {baseline_dcor:.4f}->"
            f"{recent_dcor:.4f}, jump={coupling_jump:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
