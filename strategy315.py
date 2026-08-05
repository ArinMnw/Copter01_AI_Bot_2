# -*- coding: utf-8 -*-
"""S315 - Signed-volume to return transfer-entropy release.

Transfer entropy measures whether the previous signed-volume state improves
the prediction of the next return state after conditioning on the previous
return itself.  This is directional information flow, not ordinary mutual
information or correlation.  The estimator is fitted only on bars preceding
the current closed release candle; the release must agree with the learned
conditional direction and break local structure.

Execution is market at the next bar open.  The stop is beyond the release
extreme plus an ATR buffer and the target is never below 7R.
"""

from __future__ import annotations

import math
from collections import Counter
from statistics import median

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "HISTORY_BARS": 96,
    "VOLUME_ACTIVE_RATIO": 0.90,
    "TRANSFER_ENTROPY_MIN": 0.020,
    "CONTEXT_MIN_COUNT": 6,
    "CONDITIONAL_EDGE_MIN": 0.12,
    "BREAKOUT_LOOKBACK": 10,
    "BREAKOUT_BUFFER_ATR": 0.01,
    "RELEASE_BODY_ATR_MIN": 0.55,
    "RELEASE_RANGE_ATR_MIN": 0.75,
    "RELEASE_CLOSE_FRACTION": 0.78,
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


def _sign(value):
    return 1 if value > 0.0 else (-1 if value < 0.0 else 0)


def _states(history, volume_active_ratio):
    baseline_volume = median(bar["tick_volume"] for bar in history)
    if baseline_volume <= 0.0:
        return None
    return_states = [
        _sign(history[index]["close"] - history[index - 1]["close"])
        for index in range(1, len(history))
    ]
    volume_states = []
    threshold = baseline_volume * volume_active_ratio
    for bar in history:
        body_side = _sign(bar["close"] - bar["open"])
        volume_states.append(
            body_side if bar["tick_volume"] >= threshold else 0
        )
    return return_states, volume_states


def _transfer_entropy_and_context(history, volume_active_ratio):
    """Return empirical V->R transfer entropy and next-state context counts."""
    state_data = _states(history, volume_active_ratio)
    if state_data is None:
        return None
    returns, volumes = state_data
    triples = []
    # returns[k] belongs to history[k + 1].  The corresponding predictors are
    # the prior return returns[k - 1] and prior bar volume state volumes[k].
    for index in range(1, len(returns)):
        triples.append((returns[index], returns[index - 1], volumes[index]))
    if not triples:
        return None

    triple_counts = Counter(triples)
    context_counts = Counter((prior_return, prior_volume)
                             for _, prior_return, prior_volume in triples)
    return_pair_counts = Counter((current_return, prior_return)
                                 for current_return, prior_return, _ in triples)
    prior_return_counts = Counter(prior_return
                                  for _, prior_return, _ in triples)
    total = float(len(triples))
    transfer_entropy = 0.0
    for (current_return, prior_return, prior_volume), count in triple_counts.items():
        probability = count / total
        conditional_full = count / context_counts[(prior_return, prior_volume)]
        conditional_return = (
            return_pair_counts[(current_return, prior_return)]
            / prior_return_counts[prior_return]
        )
        if conditional_full > 0.0 and conditional_return > 0.0:
            transfer_entropy += probability * math.log(
                conditional_full / conditional_return
            )

    current_prior_return = returns[-1]
    current_prior_volume = volumes[-1]
    next_counts = Counter(
        current_return
        for current_return, prior_return, prior_volume in triples
        if prior_return == current_prior_return
        and prior_volume == current_prior_volume
    )
    context_total = sum(next_counts.values())
    return transfer_entropy, next_counts, context_total


def detect_s315(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a structural release supported by directed volume information."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        history_count = max(30, int(c["HISTORY_BARS"]))
        context_min = max(1, int(c["CONTEXT_MIN_COUNT"]))
        breakout_lookback = max(3, int(c["BREAKOUT_LOOKBACK"]))
        volume_ratio = float(c["VOLUME_ACTIVE_RATIO"])
        transfer_min = float(c["TRANSFER_ENTROPY_MIN"])
        edge_min = float(c["CONDITIONAL_EDGE_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (volume_ratio, transfer_min, edge_min)
    ):
        return _wait("Invalid config: information thresholds must be finite")

    required = max(history_count + 3, period + breakout_lookback + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside liquid session")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-history_count - 1:-1]
        measured = _transfer_entropy_and_context(history, volume_ratio)
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
    if measured is None:
        return _wait("Transfer entropy is unavailable")
    transfer_entropy, next_counts, context_total = measured
    if transfer_entropy < transfer_min:
        return _wait(f"Directed information is weak ({transfer_entropy:.4f})")
    if context_total < context_min:
        return _wait(f"Conditional context is sparse ({context_total})")
    # Laplace-smoothed directional probabilities; zero returns are retained
    # in the denominator but cannot define a trade side.
    denominator = context_total + 3.0
    buy_probability = (next_counts[1] + 1.0) / denominator
    sell_probability = (next_counts[-1] + 1.0) / denominator
    conditional_edge = buy_probability - sell_probability
    if abs(conditional_edge) < edge_min:
        return _wait(f"Conditional direction is weak ({conditional_edge:.3f})")
    side = 1 if conditional_edge > 0.0 else -1

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release candle opposes the directed-information side")
    if abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if candle_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    structure = bars[-breakout_lookback - 1:-1]
    breakout_buffer = atr * float(c["BREAKOUT_BUFFER_ATR"])
    if side > 0:
        structure_level = max(bar["high"] for bar in structure)
        close_fraction = (event["close"] - event["low"]) / candle_range
        if event["close"] <= structure_level + breakout_buffer:
            return _wait("BUY release does not break structure")
    else:
        structure_level = min(bar["low"] for bar in structure)
        close_fraction = (event["high"] - event["close"]) / candle_range
        if event["close"] >= structure_level - breakout_buffer:
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
        "pattern": f"S315 {signal} Transfer Entropy Release {rr:g}R",
        "reason": (
            f"V->R transfer entropy={transfer_entropy:.5f}, "
            f"context n={context_total}, edge={conditional_edge:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
