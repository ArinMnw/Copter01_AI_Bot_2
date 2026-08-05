# -*- coding: utf-8 -*-
"""S365 - Kyle price-impact expansion release.

S365 estimates a Kyle-style price-impact slope by regressing closed returns on
signed square-root tick volume.  A recent rise versus disjoint baseline blocks
indicates that directional order-flow proxy moves price more efficiently.
Signed volume imbalance, net path, and a closed release must agree.

All price-impact and path inputs precede the release candle.  Entry is next-open
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
    "BASELINE_BARS": 80,
    "RECENT_BARS": 20,
    "KYLE_LAMBDA_RATIO_MIN": 1.18,
    "VOLUME_IMBALANCE_MIN": 0.26,
    "PATH_EFFICIENCY_MIN": 0.18,
    "NET_MOVE_ATR_MIN": 0.50,
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
    "BE_RR": 0.01,
    "CANCEL_BARS": 3,
}


def _kyle_profile(bars):
    if len(bars) < 8:
        return None
    closes = [float(bar["close"]) for bar in bars]
    if not all(math.isfinite(value) for value in closes):
        return None
    numerator = denominator = signed_volume = total_volume = 0.0
    returns = []
    for index in range(1, len(bars)):
        price_return = closes[index] - closes[index - 1]
        volume = float(bars[index].get("tick_volume", 0.0))
        if not math.isfinite(volume) or volume <= 0.0 or price_return == 0.0:
            continue
        signed_root_volume = math.copysign(math.sqrt(volume), price_return)
        numerator += signed_root_volume * price_return
        denominator += signed_root_volume * signed_root_volume
        signed_volume += signed_root_volume
        total_volume += abs(signed_root_volume)
        returns.append(price_return)
    if denominator <= 0.0 or total_volume <= 0.0 or len(returns) < 6:
        return None
    kyle_lambda = numerator / denominator
    volume_imbalance = signed_volume / total_volume
    net_move = closes[-1] - closes[0]
    if (
        kyle_lambda <= 0.0
        or abs(volume_imbalance) <= 1e-12
        or abs(net_move) <= 1e-12
    ):
        return None
    side = 1 if volume_imbalance > 0.0 else -1
    if net_move * side <= 0.0:
        return None
    travelled = sum(
        abs(closes[index] - closes[index - 1])
        for index in range(1, len(closes))
    )
    if travelled <= 0.0:
        return None
    path_efficiency = abs(net_move) / travelled
    return (
        kyle_lambda,
        abs(volume_imbalance),
        side,
        net_move,
        path_efficiency,
    )


def detect_s365(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after Kyle-style price impact expands."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        lambda_ratio_min = float(c["KYLE_LAMBDA_RATIO_MIN"])
        imbalance_min = float(c["VOLUME_IMBALANCE_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not math.isfinite(lambda_ratio_min) or lambda_ratio_min <= 0.0:
        return _wait("Invalid config: Kyle lambda ratio is invalid")
    if not math.isfinite(imbalance_min) or not 0.0 <= imbalance_min <= 1.0:
        return _wait("Invalid config: volume imbalance is invalid")

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
        baseline_lambdas = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _kyle_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_lambdas.append(profile[0])
        recent_profile = _kyle_profile(recent)
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
    if recent_profile is None or not baseline_lambdas:
        return _wait("Kyle price-impact profile is unavailable")

    kyle_lambda, imbalance, side, net_move, path_efficiency = recent_profile
    baseline_lambda = statistics.median(baseline_lambdas)
    if baseline_lambda <= 0.0:
        return _wait("Baseline Kyle lambda is zero")
    lambda_ratio = kyle_lambda / baseline_lambda
    if lambda_ratio < lambda_ratio_min:
        return _wait(f"No Kyle impact expansion ({lambda_ratio:.3f}x)")
    if imbalance < imbalance_min:
        return _wait(f"Signed volume imbalance is weak ({imbalance:.3f})")
    if path_efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Impact path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Impact path net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes Kyle impact direction")
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
        "pattern": f"S365 {signal} Kyle Impact {rr:g}R",
        "reason": (
            f"Kyle lambda={lambda_ratio:.4f}x, "
            f"imbalance={imbalance:.4f}, path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
