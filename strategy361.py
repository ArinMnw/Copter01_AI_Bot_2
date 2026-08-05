# -*- coding: utf-8 -*-
"""S361 - Rogers-Satchell drift-efficiency release.

S361 compares directional log-price drift with Rogers-Satchell intrabar
variance, an OHLC volatility estimator that remains valid under non-zero drift.
A recent increase in drift-to-volatility efficiency versus disjoint baseline
blocks indicates directional price discovery rather than noisy range expansion.

All efficiency and path inputs precede the release candle.  Entry is next-open
market, SL is beyond the closed release extreme plus ATR, and TP is at least
7R.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 60,
    "RECENT_BARS": 20,
    "RS_EFFICIENCY_MIN": 0.82,
    "RS_EFFICIENCY_INCREASE_MIN": 0.15,
    "PATH_EFFICIENCY_MIN": 0.20,
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
    "TP_RR": 7.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _rs_profile(bars):
    if len(bars) < 8:
        return None
    closes = [float(bar["close"]) for bar in bars]
    if not all(math.isfinite(value) and value > 0.0 for value in closes):
        return None
    rs_sum = 0.0
    for bar in bars:
        open_price = float(bar["open"])
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        if not all(
            math.isfinite(value) and value > 0.0
            for value in (open_price, high, low, close)
        ):
            return None
        rs_sum += (
            math.log(high / open_price) * math.log(high / close)
            + math.log(low / open_price) * math.log(low / close)
        )
    if rs_sum <= 1e-18:
        return None
    log_drift = math.log(closes[-1] / closes[0])
    if abs(log_drift) <= 1e-12:
        return None
    efficiency = abs(log_drift) / math.sqrt(rs_sum)
    net_move = closes[-1] - closes[0]
    side = 1 if net_move > 0.0 else -1
    travelled = sum(
        abs(closes[index] - closes[index - 1])
        for index in range(1, len(closes))
    )
    if travelled <= 0.0:
        return None
    path_efficiency = abs(net_move) / travelled
    return efficiency, side, net_move, path_efficiency


def detect_s361(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after Rogers-Satchell drift efficiency expands."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        efficiency_min = float(c["RS_EFFICIENCY_MIN"])
        increase_min = float(c["RS_EFFICIENCY_INCREASE_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (efficiency_min, increase_min)
    ):
        return _wait("Invalid config: Rogers-Satchell gates are invalid")

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
        baseline_efficiencies = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _rs_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_efficiencies.append(profile[0])
        recent_profile = _rs_profile(recent)
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
    if recent_profile is None or not baseline_efficiencies:
        return _wait("Rogers-Satchell profile is unavailable")

    efficiency, side, net_move, path_efficiency = recent_profile
    baseline_efficiency = statistics.median(baseline_efficiencies)
    efficiency_increase = efficiency - baseline_efficiency
    if (
        efficiency < efficiency_min
        or efficiency_increase < increase_min
    ):
        return _wait(
            f"No Rogers-Satchell efficiency expansion "
            f"({baseline_efficiency:.3f}->{efficiency:.3f}, "
            f"increase={efficiency_increase:.3f})"
        )
    if path_efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"OHLC drift path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("OHLC drift net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes OHLC drift")
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
        "pattern": f"S361 {signal} RS Drift {rr:g}R",
        "reason": (
            f"Rogers-Satchell efficiency {baseline_efficiency:.4f}->"
            f"{efficiency:.4f}, increase={efficiency_increase:.4f}, "
            f"path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
