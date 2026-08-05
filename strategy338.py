# -*- coding: utf-8 -*-
"""S338 - Multivariate price-volume PCA-coherence release.

S338 forms closed-bar features from log return, log tick-volume change, and
log relative intrabar range.  The leading eigenvalue share of their correlation
matrix measures whether recent market variation is collapsing onto one common
factor.  Rising coherence with aligned return/volume loadings precedes a
directional release.

All PCA and path inputs precede the release candle.  Entry is next-open market,
SL is beyond the closed release extreme plus ATR, and TP is at least 7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_OBSERVATIONS": 64,
    "RECENT_OBSERVATIONS": 24,
    "RECENT_PC1_SHARE_MIN": 0.50,
    "PC1_SHARE_JUMP_MIN": 0.05,
    "RETURN_LOADING_ABS_MIN": 0.35,
    "VOLUME_LOADING_ABS_MIN": 0.30,
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


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _feature_rows(bars):
    rows = []
    for index in range(1, len(bars)):
        previous_close = float(bars[index - 1]["close"])
        current_close = float(bars[index]["close"])
        previous_volume = float(bars[index - 1]["tick_volume"])
        current_volume = float(bars[index]["tick_volume"])
        candle_range = float(bars[index]["high"]) - float(bars[index]["low"])
        if (
            previous_close <= 0.0
            or current_close <= 0.0
            or previous_volume < 0.0
            or current_volume < 0.0
            or candle_range <= 0.0
        ):
            return None
        row = (
            math.log(current_close / previous_close),
            math.log((current_volume + 1.0) / (previous_volume + 1.0)),
            math.log(candle_range / current_close),
        )
        if not all(math.isfinite(value) for value in row):
            return None
        rows.append(row)
    return rows


def _pca_profile(bars):
    rows = _feature_rows(bars)
    if rows is None or len(rows) < 12:
        return None
    columns = [[row[column] for row in rows] for column in range(3)]
    means = [_mean(column) for column in columns]
    scales = [
        math.sqrt(_mean([(value - centre) ** 2 for value in column]))
        for column, centre in zip(columns, means)
    ]
    if any(scale <= 0.0 for scale in scales):
        return None
    standardized = [
        tuple(
            (row[column] - means[column]) / scales[column]
            for column in range(3)
        )
        for row in rows
    ]
    matrix = [[0.0] * 3 for _ in range(3)]
    for left in range(3):
        for right in range(3):
            matrix[left][right] = _mean([
                row[left] * row[right] for row in standardized
            ])

    vector = [1.0 / math.sqrt(3.0)] * 3
    for _ in range(30):
        candidate = [
            sum(matrix[row][column] * vector[column] for column in range(3))
            for row in range(3)
        ]
        norm = math.sqrt(sum(value * value for value in candidate))
        if norm <= 0.0:
            return None
        vector = [value / norm for value in candidate]
    eigenvalue = sum(
        vector[row] * matrix[row][column] * vector[column]
        for row in range(3)
        for column in range(3)
    )
    trace = sum(matrix[index][index] for index in range(3))
    if trace <= 0.0:
        return None
    if vector[0] < 0.0:
        vector = [-value for value in vector]
    return eigenvalue / trace, vector


def detect_s338(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after multivariate PCA coherence rises."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_OBSERVATIONS"]))
        recent_count = max(12, int(c["RECENT_OBSERVATIONS"]))
        pc1_min = float(c["RECENT_PC1_SHARE_MIN"])
        pc1_jump_min = float(c["PC1_SHARE_JUMP_MIN"])
        return_loading_min = float(c["RETURN_LOADING_ABS_MIN"])
        volume_loading_min = float(c["VOLUME_LOADING_ABS_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (
            pc1_min,
            pc1_jump_min,
            return_loading_min,
            volume_loading_min,
        )
    ):
        return _wait("Invalid config: PCA gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 3)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 2:-1]
        baseline = history[:baseline_count + 1]
        recent = history[baseline_count:]
        baseline_profile = _pca_profile(baseline)
        recent_profile = _pca_profile(recent)
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
        return _wait("PCA profile is unavailable")

    baseline_share, _ = baseline_profile
    recent_share, recent_vector = recent_profile
    share_jump = recent_share - baseline_share
    return_loading = recent_vector[0]
    volume_loading = recent_vector[1]
    if (
        recent_share < pc1_min
        or share_jump < pc1_jump_min
        or abs(return_loading) < return_loading_min
        or abs(volume_loading) < volume_loading_min
        or return_loading * volume_loading <= 0.0
    ):
        return _wait(
            f"No aligned PCA-coherence expansion "
            f"({baseline_share:.3f}->{recent_share:.3f}, "
            f"jump={share_jump:.3f}, "
            f"load={return_loading:.3f}/{volume_loading:.3f})"
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
        return _wait("Release opposes PCA-path direction")
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
        "pattern": f"S338 {signal} PCA Coherence {rr:g}R",
        "reason": (
            f"PC1 {baseline_share:.4f}->{recent_share:.4f}, "
            f"jump={share_jump:.4f}, "
            f"load={return_loading:.4f}/{volume_loading:.4f}/"
            f"{recent_vector[2]:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
