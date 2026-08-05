# -*- coding: utf-8 -*-
"""S328 - Anderson-Darling tail-weighted distribution-shift release.

The two-sample Anderson-Darling statistic compares empirical return
distributions while assigning more weight to discrepancies in the pooled
tails.  S328 estimates ordinary baseline drift from adjacent baseline halves,
then requires a materially larger baseline-to-recent shift before following a
directionally efficient closed release.

Every distribution input precedes the release candle.  Entry is next-open
market, the stop is beyond the release extreme plus ATR, and TP is at least 7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 48,
    "RECENT_RETURNS": 20,
    "RECENT_AD_MIN": 2.20,
    "AD_JUMP_MIN": 0.90,
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


def _closed_returns(bars):
    values = []
    for index in range(1, len(bars)):
        previous = float(bars[index - 1]["close"])
        current = float(bars[index]["close"])
        if previous <= 0.0 or current <= 0.0:
            return None
        values.append(math.log(current / previous))
    return values


def _anderson_darling_two_sample(first, second):
    """Return the Scholz-Stephens-style two-sample AD rank statistic."""
    first_size = len(first)
    second_size = len(second)
    total_size = first_size + second_size
    if first_size < 4 or second_size < 4:
        return None
    pooled = sorted(
        [(value, 0) for value in first]
        + [(value, 1) for value in second]
    )
    first_seen = total_seen = 0
    weighted_sum = 0.0
    group_start = 0
    while group_start < total_size:
        group_end = group_start + 1
        while (
            group_end < total_size
            and pooled[group_end][0] == pooled[group_start][0]
        ):
            group_end += 1
        first_seen += sum(
            sample == 0 for _, sample in pooled[group_start:group_end]
        )
        total_seen = group_end
        if total_seen < total_size:
            numerator = (
                total_size * first_seen - total_seen * first_size
            )
            weighted_sum += (
                numerator * numerator
                / (total_seen * (total_size - total_seen))
            )
        group_start = group_end
    return weighted_sum / (first_size * second_size)


def detect_s328(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after a tail-weighted return-distribution shift."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_RETURNS"]))
        recent_count = max(8, int(c["RECENT_RETURNS"]))
        recent_min = float(c["RECENT_AD_MIN"])
        jump_min = float(c["AD_JUMP_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and value > 0.0
        for value in (recent_min, jump_min)
    ):
        return _wait("Invalid config: AD gates must be positive and finite")

    required = max(period + 5, baseline_count + recent_count + 3)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 2:-1]
        returns = _closed_returns(history)
        baseline_returns = returns[:baseline_count]
        recent_returns = returns[baseline_count:]
        midpoint = len(baseline_returns) // 2
        baseline_ad = _anderson_darling_two_sample(
            baseline_returns[:midpoint],
            baseline_returns[midpoint:],
        )
        recent_ad = _anderson_darling_two_sample(
            baseline_returns,
            recent_returns,
        )
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
    if baseline_ad is None or recent_ad is None:
        return _wait("Anderson-Darling shift is unavailable")
    ad_jump = recent_ad - baseline_ad
    if recent_ad < recent_min or ad_jump < jump_min:
        return _wait(
            f"No tail-weighted distribution shift ({recent_ad:.3f}, "
            f"jump={ad_jump:.3f})"
        )

    recent = history[baseline_count:]
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
        return _wait("Release opposes shifted-distribution path")
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
        "pattern": f"S328 {signal} Anderson-Darling Shift {rr:g}R",
        "reason": (
            f"tail-weighted AD {baseline_ad:.4f}->{recent_ad:.4f}, "
            f"jump={ad_jump:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
