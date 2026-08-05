# -*- coding: utf-8 -*-
"""S367 - Ordinal-pattern entropy-compression release.

S367 maps every overlapping three-close sequence to one of the six possible
ordinal permutations.  A recent drop in normalized permutation entropy versus
disjoint baseline blocks indicates that price formation has become more
ordered.  Monotone-pattern imbalance, net displacement, path efficiency, and
a fully closed release candle must all agree before entry.

All entropy and path features precede the release candle.  Entry is next-open
market, SL is beyond the closed release extreme plus ATR, and TP is at least
7R.  Tick volume is deliberately unused to diversify volume-driven strategies.
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
    "ENTROPY_MAX": 0.88,
    "ENTROPY_DROP_MIN": 0.07,
    "MONOTONE_IMBALANCE_MIN": 0.08,
    "PATH_EFFICIENCY_MIN": 0.18,
    "NET_MOVE_ATR_MIN": 0.50,
    "RELEASE_BODY_ATR_MIN": 0.72,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.76,
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


def _ordinal_profile(bars):
    """Return entropy, monotone imbalance, direction, move, and efficiency."""
    if len(bars) < 8:
        return None
    closes = [float(bar["close"]) for bar in bars]
    if not all(math.isfinite(value) for value in closes):
        return None

    counts = {}
    rising = falling = 0
    for index in range(len(closes) - 2):
        triple = closes[index:index + 3]
        # The index provides a stable chronological tie-break for equal closes.
        pattern = tuple(sorted(range(3), key=lambda item: (triple[item], item)))
        counts[pattern] = counts.get(pattern, 0) + 1
        if pattern == (0, 1, 2):
            rising += 1
        elif pattern == (2, 1, 0):
            falling += 1

    observations = sum(counts.values())
    if observations <= 0:
        return None
    entropy = -sum(
        (count / observations) * math.log(count / observations)
        for count in counts.values()
    ) / math.log(6.0)
    monotone_imbalance = (rising - falling) / observations
    net_move = closes[-1] - closes[0]
    travelled = sum(
        abs(closes[index] - closes[index - 1])
        for index in range(1, len(closes))
    )
    if travelled <= 0.0 or abs(net_move) <= 1e-12:
        return None
    side = 1 if net_move > 0.0 else -1
    if monotone_imbalance * side <= 0.0:
        return None
    path_efficiency = abs(net_move) / travelled
    return entropy, abs(monotone_imbalance), side, net_move, path_efficiency


def detect_s367(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a directional release after ordinal entropy compresses."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        entropy_max = float(c["ENTROPY_MAX"])
        entropy_drop_min = float(c["ENTROPY_DROP_MIN"])
        monotone_min = float(c["MONOTONE_IMBALANCE_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not (
        math.isfinite(entropy_max)
        and 0.0 <= entropy_max <= 1.0
        and math.isfinite(entropy_drop_min)
        and entropy_drop_min >= 0.0
        and math.isfinite(monotone_min)
        and 0.0 <= monotone_min <= 1.0
    ):
        return _wait("Invalid config: entropy gates are invalid")

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
        baseline_entropies = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _ordinal_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_entropies.append(profile[0])
        recent_profile = _ordinal_profile(recent)
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
    if recent_profile is None or not baseline_entropies:
        return _wait("Ordinal profile is unavailable")

    entropy, monotone_imbalance, side, net_move, path_efficiency = recent_profile
    baseline_entropy = statistics.median(baseline_entropies)
    entropy_drop = baseline_entropy - entropy
    if entropy > entropy_max or entropy_drop < entropy_drop_min:
        return _wait(
            f"No ordinal compression ({baseline_entropy:.3f}->{entropy:.3f}, "
            f"drop={entropy_drop:.3f})"
        )
    if monotone_imbalance < monotone_min:
        return _wait(f"Monotone imbalance is weak ({monotone_imbalance:.3f})")
    if path_efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Ordered path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Ordered net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes ordinal direction")
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
        "pattern": f"S367 {signal} Ordinal Compression {rr:g}R",
        "reason": (
            f"ordinal entropy {baseline_entropy:.4f}->{entropy:.4f}, "
            f"drop={entropy_drop:.4f}, monotone={monotone_imbalance:.4f}, "
            f"path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
