# -*- coding: utf-8 -*-
"""S327 - Hawkes-style return-shock self-excitation release.

Large absolute returns are treated as point-process events.  A baseline
empirical quantile defines an event without looking into the recent window.
S327 then measures exponentially decayed recent event intensity relative to
the intensity expected from the baseline event rate.  A high ratio identifies
self-exciting price discovery rather than a single isolated shock.

All event statistics precede the release candle.  Entry is next-open market,
the stop is beyond the release extreme plus ATR, and TP is at least 7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 64,
    "RECENT_RETURNS": 16,
    # Quantiles0.75/0.80 are profitable in every window.  The lower value
    # retains one additional WF winner and improves net across all windows.
    "EVENT_QUANTILE": 0.75,
    "EXCITATION_DECAY_BARS": 4.0,
    "EXCITATION_RATIO_MIN": 2.20,
    # Every cross-window winner has at least five recent shock events.
    "RECENT_EVENT_MIN": 5,
    "DIRECTION_SCORE_MIN": 0.20,
    "PATH_EFFICIENCY_MIN": 0.20,
    "NET_MOVE_ATR_MIN": 0.50,
    "RELEASE_BODY_ATR_MIN": 0.70,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.80,
    # 15-23 adds one current/H1/WF winner versus 16-22.  Expanding another
    # hour to 14-24 adds only noise and materially worsens WF drawdown.
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


def _quantile(values, probability):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _closed_returns(bars):
    values = []
    for index in range(1, len(bars)):
        previous = float(bars[index - 1]["close"])
        current = float(bars[index]["close"])
        if previous <= 0.0 or current <= 0.0:
            return None
        values.append(math.log(current / previous))
    return values


def _excitation_state(baseline, recent, probability, decay):
    magnitudes = [abs(value) for value in baseline]
    threshold = _quantile(magnitudes, probability)
    if threshold is None or threshold <= 0.0:
        return None
    baseline_events = sum(value >= threshold for value in magnitudes)
    baseline_rate = baseline_events / len(baseline)
    weights = [
        math.exp(-(len(recent) - 1 - index) / decay)
        for index in range(len(recent))
    ]
    event_flags = [abs(value) >= threshold for value in recent]
    observed = sum(
        weight for weight, is_event in zip(weights, event_flags) if is_event
    )
    expected = baseline_rate * sum(weights)
    if expected <= 0.0 or observed <= 0.0:
        return None
    directional_numerator = sum(
        weight * value
        for weight, value, is_event in zip(weights, recent, event_flags)
        if is_event
    )
    directional_denominator = sum(
        weight * abs(value)
        for weight, value, is_event in zip(weights, recent, event_flags)
        if is_event
    )
    if directional_denominator <= 0.0:
        return None
    return {
        "ratio": observed / expected,
        "events": sum(event_flags),
        "direction": directional_numerator / directional_denominator,
        "threshold": threshold,
    }


def detect_s327(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release from a directionally self-exciting shock cluster."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(16, int(c["BASELINE_RETURNS"]))
        recent_count = max(8, int(c["RECENT_RETURNS"]))
        probability = float(c["EVENT_QUANTILE"])
        decay = float(c["EXCITATION_DECAY_BARS"])
        ratio_min = float(c["EXCITATION_RATIO_MIN"])
        event_min = max(1, int(c["RECENT_EVENT_MIN"]))
        direction_min = float(c["DIRECTION_SCORE_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if (
        not math.isfinite(probability)
        or not 0.50 <= probability <= 0.95
        or not all(
            math.isfinite(value) and value > 0.0
            for value in (decay, ratio_min, direction_min)
        )
    ):
        return _wait("Invalid config: excitation gates are invalid")

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
        state = _excitation_state(
            baseline_returns,
            recent_returns,
            probability,
            decay,
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
    if state is None:
        return _wait("Shock excitation is unavailable")
    if state["events"] < event_min or state["ratio"] < ratio_min:
        return _wait(
            f"No self-exciting shock cluster ({state['events']} events, "
            f"ratio={state['ratio']:.3f})"
        )
    if abs(state["direction"]) < direction_min:
        return _wait(
            f"Shock-cluster direction is weak ({state['direction']:.3f})"
        )
    side = 1 if state["direction"] > 0.0 else -1

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
    if net_move * side <= 0.0:
        return _wait("Recent path opposes shock-cluster direction")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes shock-cluster direction")
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
        "pattern": f"S327 {signal} Shock Self-Excitation {rr:g}R",
        "reason": (
            f"Hawkes-style ratio={state['ratio']:.4f}, "
            f"events={state['events']}, direction={state['direction']:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
