# -*- coding: utf-8 -*-
"""S395 — Spectral-Entropy Compression Release 7R.

Closed-bar returns are projected onto a compact Fourier basis.  A fall in
normalized spectral entropy, together with a rise in low-frequency energy,
identifies an auction whose formerly diffuse noise has concentrated into a
coherent directional process.  Path efficiency, displacement, participation,
and a closed release candle confirm execution.  Orders fill at the next open;
the stop is beyond the event extreme with an ATR-scaled buffer.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 84,
    "RECENT_BARS": 28,
    "SPECTRAL_BINS": 8,
    "LOW_FREQUENCY_BINS": 2,
    "SPECTRAL_ENTROPY_MAX": 0.86,
    "ENTROPY_DROP_MIN": 0.03,
    "LOW_FREQUENCY_SHARE_MIN": 0.38,
    "LOW_FREQUENCY_RISE_MIN": 0.04,
    "PATH_EFFICIENCY_MIN": 0.18,
    "NET_MOVE_ATR_MIN": 0.40,
    "EVENT_VOLUME_RATIO_MIN": 1.05,
    "EVENT_BODY_ATR_MIN": 0.65,
    "EVENT_RANGE_ATR_MIN": 0.75,
    "EVENT_BODY_FRACTION_MIN": 0.72,
    "EVENT_CLOSE_FRACTION": 0.75,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.20,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "FADE_SIGNAL": False,
    "TP_RR": 7.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _spectral_stats(bars, maximum_bins, low_bins):
    """Return normalized spectral entropy, low-bin share, and travelled path."""
    returns = [
        bars[index]["close"] - bars[index - 1]["close"]
        for index in range(1, len(bars))
    ]
    if len(returns) < 8:
        return None, None, 0.0
    mean = statistics.fmean(returns)
    centred = [value - mean for value in returns]
    bin_count = min(maximum_bins, len(centred) // 2)
    if bin_count < 2:
        return None, None, 0.0
    powers = []
    for frequency in range(1, bin_count + 1):
        real = 0.0
        imaginary = 0.0
        for index, value in enumerate(centred):
            angle = 2.0 * math.pi * frequency * index / len(centred)
            real += value * math.cos(angle)
            imaginary -= value * math.sin(angle)
        powers.append(real * real + imaginary * imaginary)
    total_power = sum(powers)
    if total_power <= 0.0 or not math.isfinite(total_power):
        return None, None, 0.0
    probabilities = [power / total_power for power in powers if power > 0.0]
    entropy = -sum(value * math.log(value) for value in probabilities)
    entropy /= math.log(bin_count)
    low_count = min(max(1, low_bins), bin_count)
    low_share = sum(powers[:low_count]) / total_power
    travelled = sum(abs(value) for value in returns)
    return entropy, low_share, travelled


def detect_s395(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S395 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        spectral_bins = max(2, int(c["SPECTRAL_BINS"]))
        low_bins = max(1, int(c["LOW_FREQUENCY_BINS"]))
        entropy_max = float(c["SPECTRAL_ENTROPY_MAX"])
        entropy_drop_min = float(c["ENTROPY_DROP_MIN"])
        low_share_min = float(c["LOW_FREQUENCY_SHARE_MIN"])
        low_rise_min = float(c["LOW_FREQUENCY_RISE_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_move_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: spectral windows are inconsistent")
    gates = (
        entropy_max, entropy_drop_min, low_share_min, low_rise_min,
        path_min, net_move_min,
    )
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: spectral gates are invalid")
    if entropy_max > 1.0 or low_share_min > 1.0:
        return _wait("Invalid config: normalized spectral gate exceeds one")
    required = max(period + 3, baseline_count + recent_count + 1)
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
        segment_count = baseline_count // recent_count
        baseline = baseline[-segment_count * recent_count:]
        baseline_stats = [
            _spectral_stats(
                baseline[index:index + recent_count], spectral_bins, low_bins
            )
            for index in range(0, len(baseline), recent_count)
        ]
        recent_entropy, recent_low_share, travelled = _spectral_stats(
            recent, spectral_bins, low_bins
        )
        baseline_entropy = statistics.median(item[0] for item in baseline_stats)
        baseline_low_share = statistics.median(item[1] for item in baseline_stats)
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if recent_entropy is None or recent_low_share is None or atr <= 0.0:
        return _wait("Spectral state or ATR is unavailable")
    entropy_drop = baseline_entropy - recent_entropy
    low_rise = recent_low_share - baseline_low_share
    if recent_entropy > entropy_max:
        return _wait(f"Recent spectral entropy is diffuse ({recent_entropy:.3f})")
    if entropy_drop < entropy_drop_min:
        return _wait(f"Spectral entropy has not compressed ({entropy_drop:.3f})")
    if recent_low_share < low_share_min:
        return _wait(f"Low-frequency energy is weak ({recent_low_share:.3f})")
    if low_rise < low_rise_min:
        return _wait(f"Low-frequency energy has not risen ({low_rise:.3f})")
    if travelled <= 0.0:
        return _wait("Recent path is zero")
    net_move = recent[-1]["close"] - recent[0]["close"]
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Auction path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Net move is too small versus ATR")
    structure_side = 1 if net_move > 0.0 else -1

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or structure_side * body <= 0.0:
        return _wait("Event does not confirm spectral direction")
    median_volume = statistics.median(float(bar["tick_volume"]) for bar in recent)
    volume_ratio = event["tick_volume"] / median_volume
    if volume_ratio < float(c["EVENT_VOLUME_RATIO_MIN"]):
        return _wait(f"Event participation is weak ({volume_ratio:.3f}x)")
    if abs(body) < atr * float(c["EVENT_BODY_ATR_MIN"]):
        return _wait("Event body is too small versus ATR")
    if candle_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Event range is too small versus ATR")
    if abs(body) / candle_range < float(c["EVENT_BODY_FRACTION_MIN"]):
        return _wait("Event release lacks body control")
    location = (
        (event["close"] - event["low"]) / candle_range
        if structure_side > 0 else (event["high"] - event["close"]) / candle_range
    )
    if location < float(c["EVENT_CLOSE_FRACTION"]):
        return _wait(f"Event close lacks directional control ({location:.3f})")

    side = -structure_side if bool(c["FADE_SIGNAL"]) else structure_side
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
        return _wait(f"Event risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Event risk too large versus price")
    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    tp = (
        math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
        if side > 0 else math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    )
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S395 {signal} Spectral-Entropy Release {rr:g}R",
        "reason": (
            f"entropy={recent_entropy:.4f}, drop={entropy_drop:.4f}, "
            f"low_share={recent_low_share:.4f}, rise={low_rise:.4f}, "
            f"path={path_efficiency:.4f}, "
            f"mode={'fade' if bool(c['FADE_SIGNAL']) else 'follow'}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
