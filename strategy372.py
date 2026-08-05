# -*- coding: utf-8 -*-
"""S372 - Realized-kurtosis directional-tail release.

S372 measures standardized realized kurtosis from closed log returns and
weights each return direction by its fourth-power tail energy.  Recent
kurtosis must expand versus disjoint baseline blocks, while signed quartic
energy, net path, and a fully closed release agree on direction.

All kurtosis and path features precede the release candle.  Entry is next-open
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
    "KURTOSIS_MIN": 3.00,
    "KURTOSIS_RATIO_MIN": 1.15,
    "DIRECTIONAL_TAIL_MIN": 0.50,
    "PATH_EFFICIENCY_MIN": 0.22,
    "NET_MOVE_ATR_MIN": 0.50,
    "RELEASE_BODY_ATR_MIN": 0.60,
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
    "BE_RR": 0.01,
    "CANCEL_BARS": 3,
}


def _kurtosis_profile(bars):
    if len(bars) < 8:
        return None
    closes = [float(bar["close"]) for bar in bars]
    if not all(math.isfinite(value) and value > 0.0 for value in closes):
        return None
    returns = [
        math.log(closes[index] / closes[index - 1])
        for index in range(1, len(closes))
    ]
    sum_squares = sum(value * value for value in returns)
    fourth_powers = [value ** 4 for value in returns]
    total_tail = sum(fourth_powers)
    if sum_squares <= 1e-24 or total_tail <= 1e-36:
        return None
    kurtosis = len(returns) * total_tail / (sum_squares * sum_squares)
    signed_tail = sum(
        value if return_value > 0.0 else -value
        for value, return_value in zip(fourth_powers, returns)
        if return_value != 0.0
    ) / total_tail
    net_move = closes[-1] - closes[0]
    travelled = sum(
        abs(closes[index] - closes[index - 1])
        for index in range(1, len(closes))
    )
    if (
        travelled <= 0.0
        or abs(net_move) <= 1e-12
        or abs(signed_tail) <= 1e-12
    ):
        return None
    side = 1 if signed_tail > 0.0 else -1
    if net_move * side <= 0.0:
        return None
    path_efficiency = abs(net_move) / travelled
    return kurtosis, abs(signed_tail), side, net_move, path_efficiency


def detect_s372(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after directional realized kurtosis expands."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        kurtosis_min = float(c["KURTOSIS_MIN"])
        kurtosis_ratio_min = float(c["KURTOSIS_RATIO_MIN"])
        directional_tail_min = float(c["DIRECTIONAL_TAIL_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (
            kurtosis_min,
            kurtosis_ratio_min,
            directional_tail_min,
        )
    ):
        return _wait("Invalid config: kurtosis gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates[-required:])
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        baseline_kurtosis = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _kurtosis_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_kurtosis.append(profile[0])
        recent_profile = _kurtosis_profile(recent)
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
    if recent_profile is None or not baseline_kurtosis:
        return _wait("Realized-kurtosis profile is unavailable")

    kurtosis, directional_tail, side, net_move, path_efficiency = recent_profile
    baseline_kurt = statistics.median(baseline_kurtosis)
    if baseline_kurt <= 0.0:
        return _wait("Baseline realized kurtosis is zero")
    kurtosis_ratio = kurtosis / baseline_kurt
    if kurtosis < kurtosis_min or kurtosis_ratio < kurtosis_ratio_min:
        return _wait(
            f"No kurtosis expansion ({baseline_kurt:.3f}->{kurtosis:.3f}, "
            f"ratio={kurtosis_ratio:.3f})"
        )
    if directional_tail < directional_tail_min:
        return _wait(f"Directional tail energy is weak ({directional_tail:.3f})")
    if path_efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Fat-tail path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Fat-tail net move is too small")

    body = float(event["close"]) - float(event["open"])
    candle_range = float(event["high"]) - float(event["low"])
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes kurtosis-tail direction")
    if abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if candle_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    close_fraction = (
        (float(event["close"]) - float(event["low"])) / candle_range
        if side > 0
        else (float(event["high"]) - float(event["close"])) / candle_range
    )
    if close_fraction < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Release lacks directional close control")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(float(event["close"]), 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor(
            (float(event["low"]) - sl_buffer + 1e-12) * 100.0
        ) / 100.0
    else:
        sl = math.ceil(
            (float(event["high"]) + sl_buffer - 1e-12) * 100.0
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
        "pattern": f"S372 {signal} Realized Kurtosis {rr:g}R",
        "reason": (
            f"realized kurtosis {baseline_kurt:.4f}->{kurtosis:.4f}, "
            f"ratio={kurtosis_ratio:.4f}, directional={directional_tail:.4f}, "
            f"path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
