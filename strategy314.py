# -*- coding: utf-8 -*-
"""S314 - Renewal-drought participation shock breakout.

Institutional expansion candles are treated as arrivals in a renewal process.
The detector estimates the empirical distribution of closed-bar waiting times
between prior range-and-volume shocks.  It follows only the first structural
breakout shock after an unusually long quiet interval, where accumulated
inventory is most likely to require rapid repricing.

Each historical shock uses ATR and volume information available strictly
before that candle.  Entry is market at the next bar open in the conservative
repository replay, with a structural release-candle stop and TP of at least 7R.
"""

from __future__ import annotations

import math
from statistics import median

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "VOLUME_LOOKBACK": 24,
    "EVENT_LOOKBACK": 120,
    "EVENT_RANGE_ATR_MIN": 1.10,
    "EVENT_VOLUME_RATIO_MIN": 1.00,
    "MIN_HISTORICAL_GAPS": 5,
    "DROUGHT_GAP_QUANTILE": 0.65,
    "DROUGHT_MIN_BARS": 5,
    "BREAKOUT_LOOKBACK": 12,
    "BREAKOUT_BUFFER_ATR": 0.02,
    "RELEASE_BODY_ATR_MIN": 0.55,
    "RELEASE_CLOSE_FRACTION": 0.75,
    "SESSION_START_HOUR": 7,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.80,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 8.0,
    "BE_RR": 0.10,
    "CANCEL_BARS": 3,
}


def _quantile(values, probability):
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _shock_indices(bars, period, volume_lookback, range_min, volume_min):
    """Return shock indices using only each candle's preceding information."""
    start = max(period + 1, volume_lookback)
    output = []
    for index in range(start, len(bars)):
        prior_atr = _atr(bars[:index], period)
        prior_volume = median(
            bar["tick_volume"]
            for bar in bars[index - volume_lookback:index]
        )
        if prior_atr <= 0.0 or prior_volume <= 0.0:
            continue
        candle = bars[index]
        range_ratio = (candle["high"] - candle["low"]) / prior_atr
        volume_ratio = candle["tick_volume"] / prior_volume
        if range_ratio >= range_min and volume_ratio >= volume_min:
            output.append(index)
    return output


def detect_s314(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a structural participation shock after a renewal drought."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        volume_lookback = max(4, int(c["VOLUME_LOOKBACK"]))
        event_lookback = max(30, int(c["EVENT_LOOKBACK"]))
        minimum_gaps = max(3, int(c["MIN_HISTORICAL_GAPS"]))
        breakout_lookback = max(3, int(c["BREAKOUT_LOOKBACK"]))
        drought_quantile = float(c["DROUGHT_GAP_QUANTILE"])
        range_min = float(c["EVENT_RANGE_ATR_MIN"])
        volume_min = float(c["EVENT_VOLUME_RATIO_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not 0.0 <= drought_quantile <= 1.0:
        return _wait("Invalid config: drought quantile must be in [0, 1]")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (range_min, volume_min)
    ):
        return _wait("Invalid config: event thresholds must be finite")

    required = max(
        event_lookback + period + volume_lookback + 3,
        breakout_lookback + period + 5,
    )
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside liquid session")
    try:
        bars = _bars(rates)
        sample = bars[-(event_lookback + period + volume_lookback + 1):]
        shocks = _shock_indices(
            sample, period, volume_lookback, range_min, volume_min
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
    current_index = len(sample) - 1
    if not shocks or shocks[-1] != current_index:
        return _wait("Current candle is not a participation shock")
    prior_shocks = shocks[:-1]
    historical_gaps = [
        prior_shocks[index] - prior_shocks[index - 1]
        for index in range(1, len(prior_shocks))
    ]
    if len(historical_gaps) < minimum_gaps:
        return _wait("Not enough historical renewal gaps")
    current_gap = current_index - prior_shocks[-1]
    drought_floor = _quantile(historical_gaps, drought_quantile)
    if drought_floor is None:
        return _wait("Renewal drought threshold unavailable")
    required_gap = max(float(c["DROUGHT_MIN_BARS"]), drought_floor)
    if current_gap < required_gap:
        return _wait(
            f"Renewal interval is ordinary ({current_gap} < {required_gap:.2f})"
        )

    event = bars[-1]
    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Shock body is too small")
    side = 1 if body > 0.0 else -1
    structure = bars[-breakout_lookback - 1:-1]
    buffer = atr * float(c["BREAKOUT_BUFFER_ATR"])
    if side > 0:
        structure_level = max(bar["high"] for bar in structure)
        close_fraction = (event["close"] - event["low"]) / candle_range
        if event["close"] <= structure_level + buffer:
            return _wait("Bull shock does not close above structure")
    else:
        structure_level = min(bar["low"] for bar in structure)
        close_fraction = (event["high"] - event["close"]) / candle_range
        if event["close"] >= structure_level - buffer:
            return _wait("Bear shock does not close below structure")
    if close_fraction < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Shock lacks directional close control")

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
        return _wait(f"Shock risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Shock risk too large versus price")

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
        "pattern": f"S314 {signal} Renewal Drought Shock {rr:g}R",
        "reason": (
            f"renewal gap={current_gap}, q{drought_quantile:.2f}="
            f"{drought_floor:.2f}, structure={structure_level:.2f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
