# -*- coding: utf-8 -*-
"""S325 - Kendall volatility-clustering release.

Kendall tau-b between |return_t| and |return_t+1| is a robust measure of
volatility persistence.  S325 compares non-overlapping baseline and recent
samples, then follows a strong closed release in the recent path direction
when rank-based volatility clustering appears.

All statistics precede the release candle.  Entry is next-open market, the
stop is beyond the release extreme plus ATR, and TP is at least 7R.
"""

from __future__ import annotations

import math
from collections import Counter

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 48,
    "RECENT_RETURNS": 20,
    "RECENT_TAU_MIN": 0.16,
    "TAU_JUMP_MIN": 0.14,
    "PATH_EFFICIENCY_MIN": 0.22,
    "NET_MOVE_ATR_MIN": 0.55,
    "RELEASE_BODY_ATR_MIN": 0.72,
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
    "TP_RR": 8.0,
    "BE_RR": 0.08,
    "CANCEL_BARS": 3,
}


def _kendall_tau_b_fast(first, second):
    """Return exact tau-b using tie counts and a Fenwick inversion count."""
    if len(first) != len(second) or len(first) < 4:
        return None
    size = len(first)
    total_pairs = size * (size - 1) // 2
    first_ties = sum(
        count * (count - 1) // 2
        for count in Counter(first).values()
    )
    second_ties = sum(
        count * (count - 1) // 2
        for count in Counter(second).values()
    )
    joint_ties = sum(
        count * (count - 1) // 2
        for count in Counter(zip(first, second)).values()
    )
    denominator = math.sqrt(
        (total_pairs - first_ties) * (total_pairs - second_ties)
    )
    if denominator <= 0.0:
        return None

    ordered = sorted(zip(first, second))
    second_levels = {
        value: index + 1
        for index, value in enumerate(sorted(set(second)))
    }
    tree = [0] * (len(second_levels) + 1)

    def prefix_sum(index):
        result = 0
        while index > 0:
            result += tree[index]
            index -= index & -index
        return result

    def add(index):
        while index < len(tree):
            tree[index] += 1
            index += index & -index

    discordant = inserted = 0
    group_start = 0
    while group_start < size:
        group_end = group_start + 1
        while (
            group_end < size
            and ordered[group_end][0] == ordered[group_start][0]
        ):
            group_end += 1
        for _, second_value in ordered[group_start:group_end]:
            rank = second_levels[second_value]
            discordant += inserted - prefix_sum(rank)
        for _, second_value in ordered[group_start:group_end]:
            add(second_levels[second_value])
            inserted += 1
        group_start = group_end

    numerator = (
        total_pairs - first_ties - second_ties + joint_ties
        - 2 * discordant
    )
    return numerator / denominator


def _volatility_tau(bars):
    magnitudes = []
    for index in range(1, len(bars)):
        previous = float(bars[index - 1]["close"])
        current = float(bars[index]["close"])
        if previous <= 0.0 or current <= 0.0:
            return None
        magnitudes.append(abs(math.log(current / previous)))
    if len(magnitudes) < 8:
        return None
    return _kendall_tau_b_fast(magnitudes[:-1], magnitudes[1:])


def detect_s325(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after rank-based volatility clustering increases."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(8, int(c["BASELINE_RETURNS"]))
        recent_count = max(8, int(c["RECENT_RETURNS"]))
        recent_min = float(c["RECENT_TAU_MIN"])
        jump_min = float(c["TAU_JUMP_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (recent_min, jump_min)
    ):
        return _wait("Invalid config: Kendall gates must be finite")

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
        baseline_tau = _volatility_tau(baseline)
        recent_tau = _volatility_tau(recent)
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
    if baseline_tau is None or recent_tau is None:
        return _wait("Volatility Kendall tau is unavailable")
    tau_jump = recent_tau - baseline_tau
    if recent_tau < recent_min or tau_jump < jump_min:
        return _wait(
            f"No volatility-clustering shift ({recent_tau:.3f}, "
            f"jump={tau_jump:.3f})"
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
        return _wait("Release opposes volatility-cluster path")
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
        "pattern": f"S325 {signal} Volatility Clustering {rr:g}R",
        "reason": (
            f"absolute-return tau {baseline_tau:.4f}->{recent_tau:.4f}, "
            f"jump={tau_jump:.4f}"
        ),
        "be_rr": (
            None if c.get("BE_RR") is None else float(c["BE_RR"])
        ),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
