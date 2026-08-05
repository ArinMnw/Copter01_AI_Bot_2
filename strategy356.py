# -*- coding: utf-8 -*-
"""S356 - Markov sign-entropy compression release.

S356 models the signs of closed-to-closed returns as a two-state Markov chain.
It looks for a recent fall in conditional transition entropy versus disjoint
baseline blocks, together with increased same-sign persistence and directional
occupation.  This represents an auction becoming easier to predict before a
closed directional release.

All Markov and path inputs precede the release candle.  Entry is next-open
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
    "RECENT_ENTROPY_MAX": 0.85,
    "ENTROPY_DROP_MIN": 0.10,
    "PERSISTENCE_MIN": 0.58,
    "DIRECTIONAL_BALANCE_MIN": 0.20,
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
    "TP_RR": 8.0,
    "BE_RR": 0.08,
    "CANCEL_BARS": 3,
}


def _binary_entropy(probability):
    if probability <= 0.0 or probability >= 1.0:
        return 0.0
    return -(
        probability * math.log2(probability)
        + (1.0 - probability) * math.log2(1.0 - probability)
    )


def _markov_profile(bars):
    if len(bars) < 8:
        return None
    closes = [float(bar["close"]) for bar in bars]
    if not all(math.isfinite(value) for value in closes):
        return None
    returns = [
        closes[index] - closes[index - 1]
        for index in range(1, len(closes))
    ]
    signs = [1 if value > 0.0 else -1 for value in returns if value != 0.0]
    if len(signs) < 6:
        return None
    counts = {
        (1, 1): 0,
        (1, -1): 0,
        (-1, 1): 0,
        (-1, -1): 0,
    }
    for previous, current in zip(signs, signs[1:]):
        counts[(previous, current)] += 1
    transitions = len(signs) - 1
    conditional_entropy = 0.0
    for previous in (-1, 1):
        state_total = counts[(previous, -1)] + counts[(previous, 1)]
        if state_total:
            probability_up = counts[(previous, 1)] / state_total
            conditional_entropy += (
                state_total / transitions
                * _binary_entropy(probability_up)
            )
    persistence = (
        counts[(1, 1)] + counts[(-1, -1)]
    ) / transitions
    signed_balance = sum(signs) / len(signs)
    net_move = closes[-1] - closes[0]
    if abs(net_move) <= 1e-12 or signed_balance == 0.0:
        return None
    side = 1 if net_move > 0.0 else -1
    if signed_balance * side <= 0.0:
        return None
    travelled = sum(abs(value) for value in returns)
    if travelled <= 0.0:
        return None
    efficiency = abs(net_move) / travelled
    return (
        conditional_entropy,
        persistence,
        abs(signed_balance),
        side,
        net_move,
        efficiency,
    )


def detect_s356(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after directional Markov entropy compresses."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        entropy_max = float(c["RECENT_ENTROPY_MAX"])
        entropy_drop_min = float(c["ENTROPY_DROP_MIN"])
        persistence_min = float(c["PERSISTENCE_MIN"])
        balance_min = float(c["DIRECTIONAL_BALANCE_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (
            entropy_max,
            entropy_drop_min,
            persistence_min,
            balance_min,
        )
    ):
        return _wait("Invalid config: Markov gates are invalid")

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
            profile = _markov_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_entropies.append(profile[0])
        recent_profile = _markov_profile(recent)
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
        return _wait("Markov profile is unavailable")

    entropy, persistence, balance, side, net_move, efficiency = recent_profile
    baseline_entropy = statistics.median(baseline_entropies)
    entropy_drop = baseline_entropy - entropy
    if entropy > entropy_max or entropy_drop < entropy_drop_min:
        return _wait(
            f"No Markov entropy compression "
            f"({baseline_entropy:.3f}->{entropy:.3f}, "
            f"drop={entropy_drop:.3f})"
        )
    if persistence < persistence_min:
        return _wait(f"Return signs lack persistence ({persistence:.3f})")
    if balance < balance_min:
        return _wait(f"Directional sign balance is weak ({balance:.3f})")
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Markov path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Markov net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes Markov direction")
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
        "pattern": f"S356 {signal} Markov Compression {rr:g}R",
        "reason": (
            f"Markov entropy {baseline_entropy:.4f}->{entropy:.4f}, "
            f"drop={entropy_drop:.4f}, persistence={persistence:.4f}, "
            f"balance={balance:.4f}, efficiency={efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
