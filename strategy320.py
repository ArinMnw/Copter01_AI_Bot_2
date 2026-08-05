# -*- coding: utf-8 -*-
"""S320 - Spectral-entropy compression release.

The normalized entropy of a return periodogram distinguishes broadband,
noise-like price discovery from paths whose energy is concentrated in fewer
frequencies.  S320 follows a structural release when a high-entropy baseline
compresses into a directionally efficient low-entropy recent regime.

The DFT uses only closed returns preceding the release candle.  Entry is
next-open market, with a release-extreme ATR stop and TP of at least 7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 64,
    "RECENT_RETURNS": 32,
    "BASELINE_ENTROPY_MIN": 0.82,
    "RECENT_ENTROPY_MAX": 0.88,
    "ENTROPY_DROP_MIN": 0.04,
    "PATH_EFFICIENCY_MIN": 0.30,
    "NET_MOVE_ATR_MIN": 0.70,
    "BREAKOUT_LOOKBACK": 10,
    "BREAKOUT_BUFFER_ATR": 0.01,
    "RELEASE_BODY_ATR_MIN": 0.60,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.80,
    "SESSION_START_HOUR": 7,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 8.0,
    "BE_RR": 0.10,
    "CANCEL_BARS": 3,
}


def _spectral_entropy(values):
    size = len(values)
    if size < 8:
        return None
    mean_value = sum(values) / size
    centered = [value - mean_value for value in values]
    powers = []
    for frequency in range(1, size // 2 + 1):
        real = imaginary = 0.0
        for index, value in enumerate(centered):
            angle = 2.0 * math.pi * frequency * index / size
            real += value * math.cos(angle)
            imaginary -= value * math.sin(angle)
        powers.append(real * real + imaginary * imaginary)
    total_power = sum(powers)
    if total_power <= 0.0 or len(powers) < 2:
        return None
    probabilities = [
        power / total_power for power in powers if power > 0.0
    ]
    entropy = -sum(
        probability * math.log(probability)
        for probability in probabilities
    )
    return entropy / math.log(len(powers))


def detect_s320(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a structural release after frequency-energy concentration."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_RETURNS"]))
        recent_count = max(8, int(c["RECENT_RETURNS"]))
        breakout_lookback = max(3, int(c["BREAKOUT_LOOKBACK"]))
        baseline_min = float(c["BASELINE_ENTROPY_MIN"])
        recent_max = float(c["RECENT_ENTROPY_MAX"])
        drop_min = float(c["ENTROPY_DROP_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (baseline_min, recent_max, drop_min)
    ):
        return _wait("Invalid config: entropy thresholds must be in [0, 1]")

    total_returns = baseline_count + recent_count
    required = max(total_returns + 4, period + breakout_lookback + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside liquid session")
    try:
        bars = _bars(rates)
        event = bars[-1]
        closes = [
            bar["close"] for bar in bars[-total_returns - 2:-1]
        ]
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
        baseline = returns[:baseline_count]
        recent = returns[baseline_count:]
        baseline_entropy = _spectral_entropy(baseline)
        recent_entropy = _spectral_entropy(recent)
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
    if baseline_entropy is None or recent_entropy is None:
        return _wait("Spectral entropy is unavailable")
    entropy_drop = baseline_entropy - recent_entropy
    if baseline_entropy < baseline_min:
        return _wait(f"Baseline spectrum is already concentrated ({baseline_entropy:.3f})")
    if recent_entropy > recent_max or entropy_drop < drop_min:
        return _wait(
            f"No spectral compression ({recent_entropy:.3f}, "
            f"drop={entropy_drop:.3f})"
        )

    recent_bars = bars[-recent_count - 1:-1]
    net_move = recent_bars[-1]["close"] - recent_bars[0]["close"]
    travelled = sum(
        abs(recent_bars[index]["close"] - recent_bars[index - 1]["close"])
        for index in range(1, len(recent_bars))
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
        return _wait("Release opposes the spectrally organized path")
    if abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if candle_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    structure = bars[-breakout_lookback - 1:-1]
    buffer = atr * float(c["BREAKOUT_BUFFER_ATR"])
    if side > 0:
        structure_level = max(bar["high"] for bar in structure)
        close_fraction = (event["close"] - event["low"]) / candle_range
        if event["close"] <= structure_level + buffer:
            return _wait("BUY release does not break structure")
    else:
        structure_level = min(bar["low"] for bar in structure)
        close_fraction = (event["high"] - event["close"]) / candle_range
        if event["close"] >= structure_level - buffer:
            return _wait("SELL release does not break structure")
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
        "pattern": f"S320 {signal} Spectral Entropy Release {rr:g}R",
        "reason": (
            f"spectral entropy {baseline_entropy:.4f}->"
            f"{recent_entropy:.4f}, efficiency={efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
