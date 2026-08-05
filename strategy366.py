# -*- coding: utf-8 -*-
"""S366 - VPIN-style volume-toxicity release.

S366 allocates signed tick volume into equal-volume buckets and averages each
bucket's absolute buy-sell imbalance as a VPIN-style toxicity proxy.  Recent
toxicity must rise versus disjoint baseline blocks while aggregate signed
volume, net path, and a closed release agree on direction.

All volume-toxicity and path inputs precede the release candle.  Entry is
next-open market, SL is beyond the closed release extreme plus ATR, and TP is
at least 7R.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 120,
    "RECENT_BARS": 20,
    "VOLUME_BUCKETS": 4,
    "VPIN_MIN": 0.34,
    "VPIN_RATIO_MIN": 1.15,
    "DIRECTIONAL_VOLUME_MIN": 0.34,
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
    "TP_RR": 9.0,
    "BE_RR": 0.01,
    "CANCEL_BARS": 3,
}


def _vpin_profile(bars, bucket_count):
    if len(bars) < 8 or bucket_count < 2:
        return None
    closes = [float(bar["close"]) for bar in bars]
    if not all(math.isfinite(value) for value in closes):
        return None
    observations = []
    for index in range(1, len(bars)):
        volume = float(bars[index].get("tick_volume", 0.0))
        price_return = closes[index] - closes[index - 1]
        if not math.isfinite(volume) or volume <= 0.0 or price_return == 0.0:
            continue
        observations.append((volume, 1 if price_return > 0.0 else -1))
    total_volume = sum(volume for volume, _ in observations)
    if len(observations) < 6 or total_volume <= 0.0:
        return None
    target = total_volume / bucket_count
    buckets = []
    bucket_volume = bucket_signed = 0.0
    for observation_volume, sign in observations:
        remaining = observation_volume
        while remaining > 1e-12 and len(buckets) < bucket_count:
            capacity = target - bucket_volume
            allocation = min(remaining, capacity)
            bucket_volume += allocation
            bucket_signed += sign * allocation
            remaining -= allocation
            if bucket_volume >= target - 1e-9:
                buckets.append(abs(bucket_signed) / bucket_volume)
                bucket_volume = bucket_signed = 0.0
    if bucket_volume > 1e-9 and len(buckets) < bucket_count:
        buckets.append(abs(bucket_signed) / bucket_volume)
    if len(buckets) < 2:
        return None
    vpin = sum(buckets) / len(buckets)
    signed_volume = sum(volume * sign for volume, sign in observations)
    directional_volume = signed_volume / total_volume
    net_move = closes[-1] - closes[0]
    if abs(directional_volume) <= 1e-12 or abs(net_move) <= 1e-12:
        return None
    side = 1 if directional_volume > 0.0 else -1
    if net_move * side <= 0.0:
        return None
    travelled = sum(
        abs(closes[index] - closes[index - 1])
        for index in range(1, len(closes))
    )
    if travelled <= 0.0:
        return None
    path_efficiency = abs(net_move) / travelled
    return vpin, abs(directional_volume), side, net_move, path_efficiency


def detect_s366(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after VPIN-style volume toxicity expands."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        bucket_count = max(2, int(c["VOLUME_BUCKETS"]))
        vpin_min = float(c["VPIN_MIN"])
        vpin_ratio_min = float(c["VPIN_RATIO_MIN"])
        directional_volume_min = float(c["DIRECTIONAL_VOLUME_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (vpin_min, vpin_ratio_min, directional_volume_min)
    ):
        return _wait("Invalid config: VPIN gates are invalid")

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
        baseline_vpins = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _vpin_profile(
                baseline[start:start + recent_count],
                bucket_count,
            )
            if profile is not None:
                baseline_vpins.append(profile[0])
        recent_profile = _vpin_profile(recent, bucket_count)
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
    if recent_profile is None or not baseline_vpins:
        return _wait("VPIN profile is unavailable")

    vpin, directional_volume, side, net_move, path_efficiency = recent_profile
    baseline_vpin = statistics.median(baseline_vpins)
    if baseline_vpin <= 0.0:
        return _wait("Baseline VPIN is zero")
    vpin_ratio = vpin / baseline_vpin
    if vpin < vpin_min or vpin_ratio < vpin_ratio_min:
        return _wait(
            f"No VPIN expansion ({baseline_vpin:.3f}->{vpin:.3f}, "
            f"ratio={vpin_ratio:.3f})"
        )
    if directional_volume < directional_volume_min:
        return _wait(f"Directional volume is weak ({directional_volume:.3f})")
    if path_efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Toxic-volume path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Toxic-volume net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes VPIN direction")
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
        "pattern": f"S366 {signal} VPIN Toxicity {rr:g}R",
        "reason": (
            f"VPIN {baseline_vpin:.4f}->{vpin:.4f}, "
            f"ratio={vpin_ratio:.4f}, directional={directional_volume:.4f}, "
            f"path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
