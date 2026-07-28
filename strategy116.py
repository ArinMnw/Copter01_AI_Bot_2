# -*- coding: utf-8 -*-
"""S116 — Session VWAP Delta-Divergence Exhaustion Fade.

S115 follows structural BOS/FVG continuation when counter-flow cannot return
to an imbalance.  S116 deliberately diversifies that exposure: it fades a
late-session price extension only when session-anchored VWAP deviation,
tick-volume delta divergence, and a closed rejection candle agree.

The detector is pure.  It consumes only chronological, fully closed MT5 bars.
It emits a limit order, leaving spread-aware fills and same-bar SL-first
evaluation to the backtest/execution layer.
"""

from __future__ import annotations

import math
from datetime import timedelta
from statistics import median


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_ANCHOR_HOUR": 14,
    "SESSION_MIN_BARS": 24,
    "TRADE_HOURS": (20, 21, 22, 23),
    "TIME_FILTER_ENABLED": True,
    # Session VWAP extension
    "VWAP_Z_MIN": 1.80,
    "VWAP_STD_FLOOR_ATR": 0.25,
    # Price/volume-delta divergence
    "DIVERGENCE_BARS": 6,
    "EXTREME_BREAK_ATR": 0.05,
    "DELTA_DIVERGENCE_MIN": 0.12,
    # Rejection confirmation on the latest closed candle
    "REJECTION_WICK_RATIO": 0.30,
    "REJECTION_CLOSE_LOCATION": 0.58,
    "REJECTION_BODY_ATR": 0.05,
    "REJECTION_VOLUME_MULT": 0.75,
    # Limit execution and dynamic risk
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.25,
    "MAX_RISK_ATR": 2.50,
    "TP_RR": 1.60,
    "TP_MAX_RR": 2.50,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
    # Optional repository ML gate
    "ML_FILTER_ENABLED": False,
    "ML_SCORE_THRESHOLD": 0.55,
    "ML_SYMBOL": "XAUUSD.iux",
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("non-finite numeric value")
    return value


def _normalise_rates(rates):
    bars, previous_time = [], None
    for raw in rates:
        timestamp = int(_finite(raw["time"]))
        if previous_time is not None and timestamp <= previous_time:
            raise ValueError("rates must have strictly increasing timestamps")
        previous_time = timestamp
        bar = {
            "time": timestamp,
            "open": _finite(raw["open"]),
            "high": _finite(raw["high"]),
            "low": _finite(raw["low"]),
            "close": _finite(raw["close"]),
            "tick_volume": max(0.0, _finite(raw["tick_volume"])),
        }
        if bar["high"] < max(bar["open"], bar["close"], bar["low"]):
            raise ValueError("high is below another OHLC value")
        if bar["low"] > min(bar["open"], bar["close"], bar["high"]):
            raise ValueError("low is above another OHLC value")
        bars.append(bar)
    return bars


def _atr(bars, period):
    if period < 1 or len(bars) < period + 1:
        return 0.0
    values = []
    for index in range(len(bars) - period, len(bars)):
        bar, previous_close = bars[index], bars[index - 1]["close"]
        values.append(max(
            bar["high"] - bar["low"],
            abs(bar["high"] - previous_close),
            abs(bar["low"] - previous_close),
        ))
    return sum(values) / len(values)


def _clv(bar):
    spread = bar["high"] - bar["low"]
    if spread <= 0.0:
        return 0.0
    return max(-1.0, min(
        1.0,
        (2.0 * bar["close"] - bar["high"] - bar["low"]) / spread,
    ))


def _normalised_delta(bars):
    volume = sum(bar["tick_volume"] for bar in bars)
    if volume <= 0.0:
        return 0.0
    return sum(_clv(bar) * bar["tick_volume"] for bar in bars) / volume


def _session_vwap(bars):
    weights = [bar["tick_volume"] for bar in bars]
    if sum(weights) <= 0.0:
        weights = [1.0] * len(bars)
    prices = [(bar["high"] + bar["low"] + bar["close"]) / 3.0 for bar in bars]
    weight_sum = sum(weights)
    vwap = sum(price * weight for price, weight in zip(prices, weights)) / weight_sum
    variance = sum(
        weight * (price - vwap) ** 2
        for price, weight in zip(prices, weights)
    ) / weight_sum
    return vwap, math.sqrt(max(0.0, variance))


def _ml_allows(cfg, rates, tf, direction, entry, dt_bkk):
    if not bool(cfg["ML_FILTER_ENABLED"]):
        return True, None
    try:
        import ml_scoring

        probability = float(ml_scoring.score_signal(
            cfg["ML_SYMBOL"], tf, direction, entry, dt_bkk,
            historical_rates=rates,
        ))
    except Exception:
        return False, None
    return probability >= float(cfg["ML_SCORE_THRESHOLD"]), probability


def _validate_cfg(cfg):
    integer_keys = ("ATR_PERIOD", "SESSION_ANCHOR_HOUR", "SESSION_MIN_BARS",
                    "DIVERGENCE_BARS")
    integers = {}
    for key in integer_keys:
        raw = _finite(cfg[key])
        if raw != int(raw):
            raise ValueError(f"{key} must be an integer")
        integers[key] = int(raw)
    if integers["ATR_PERIOD"] < 1 or integers["SESSION_MIN_BARS"] < 2:
        raise ValueError("ATR_PERIOD and SESSION_MIN_BARS are too small")
    if integers["DIVERGENCE_BARS"] < 2:
        raise ValueError("DIVERGENCE_BARS must be at least 2")
    if not 0 <= integers["SESSION_ANCHOR_HOUR"] <= 23:
        raise ValueError("SESSION_ANCHOR_HOUR must be from 0 to 23")

    numeric_keys = (
        "VWAP_Z_MIN", "VWAP_STD_FLOOR_ATR", "EXTREME_BREAK_ATR",
        "DELTA_DIVERGENCE_MIN", "REJECTION_WICK_RATIO",
        "REJECTION_CLOSE_LOCATION", "REJECTION_BODY_ATR",
        "REJECTION_VOLUME_MULT", "ENTRY_RANGE_FRACTION", "SL_BUFFER_ATR",
        "MAX_RISK_ATR", "TP_RR", "TP_MAX_RR", "ML_SCORE_THRESHOLD",
    )
    numbers = {key: _finite(cfg[key]) for key in numeric_keys}
    if any(value < 0.0 for value in numbers.values()):
        raise ValueError("numeric cfg values cannot be negative")
    fractions = ("REJECTION_WICK_RATIO", "REJECTION_CLOSE_LOCATION",
                 "ENTRY_RANGE_FRACTION", "ML_SCORE_THRESHOLD")
    if any(not 0.0 <= numbers[key] <= 1.0 for key in fractions):
        raise ValueError("ratio cfg values must be between 0 and 1")
    if numbers["TP_RR"] < 1.5 or numbers["TP_MAX_RR"] < numbers["TP_RR"]:
        raise ValueError("TP_RR must be >=1.5 and TP_MAX_RR >= TP_RR")
    if numbers["MAX_RISK_ATR"] <= 0.0:
        raise ValueError("MAX_RISK_ATR must be positive")
    if cfg["BE_RR"] is not None and _finite(cfg["BE_RR"]) <= 0.0:
        raise ValueError("BE_RR must be positive or None")
    if cfg["CANCEL_BARS"] is not None:
        cancel = _finite(cfg["CANCEL_BARS"])
        if cancel != int(cancel) or cancel < 1:
            raise ValueError("CANCEL_BARS must be a positive integer or None")
    hours = tuple(cfg["TRADE_HOURS"])
    if any(int(hour) != hour or not 0 <= int(hour) <= 23 for hour in hours):
        raise ValueError("TRADE_HOURS contains an invalid hour")
    return integers


def _trade(direction, entry, sl, tp, cfg, reason):
    entry_r, sl_r = round(entry, 2), round(sl, 2)
    risk = entry_r - sl_r if direction == "BUY" else sl_r - entry_r
    if risk <= 0.0:
        return _wait("Invalid risk after price rounding")
    minimum_rr = max(1.5, float(cfg["TP_RR"]))
    if direction == "BUY":
        minimum_tp = entry_r + minimum_rr * risk
        tp_r = math.ceil((max(tp, minimum_tp) - 1e-12) * 100.0) / 100.0
    else:
        maximum_tp = entry_r - minimum_rr * risk
        tp_r = math.floor((min(tp, maximum_tp) + 1e-12) * 100.0) / 100.0
    return {
        "signal": direction,
        "entry": entry_r,
        "sl": sl_r,
        "tp": tp_r,
        "order_type": "limit",
        "pattern": f"S116 {'Bull' if direction == 'BUY' else 'Bear'} VWAP DeltaDiv",
        "reason": reason,
        "be_rr": float(cfg["BE_RR"]) if cfg["BE_RR"] is not None else None,
        "cancel_bars": (int(cfg["CANCEL_BARS"])
                        if cfg["CANCEL_BARS"] is not None else None),
    }


def detect_s116(rates, tf, dt_bkk, cfg):
    """Detect a closed-bar S116 session exhaustion setup."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        windows = _validate_cfg(c)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid cfg: {exc}")
    required = max(
        windows["ATR_PERIOD"] + 1,
        windows["SESSION_MIN_BARS"],
        windows["DIVERGENCE_BARS"] * 2,
    )
    if rates is None or len(rates) < required:
        return _wait(f"Not enough data ({0 if rates is None else len(rates)}/{required})")
    if dt_bkk is None or dt_bkk.tzinfo is None:
        return _wait("timezone-aware dt_bkk is required")
    try:
        if bool(c["TIME_FILTER_ENABLED"]) and dt_bkk.hour not in tuple(c["TRADE_HOURS"]):
            return _wait(f"Outside trade hours ({dt_bkk.hour:02d}:00 BKK)")
        bars = _normalise_rates(rates)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid input: {exc}")

    anchor = dt_bkk.replace(
        hour=windows["SESSION_ANCHOR_HOUR"], minute=0, second=0, microsecond=0,
    )
    if dt_bkk < anchor:
        anchor -= timedelta(days=1)
    session = [bar for bar in bars if bar["time"] >= int(anchor.timestamp())]
    if len(session) < windows["SESSION_MIN_BARS"]:
        return _wait(f"Session has only {len(session)} closed bars")

    atr = _atr(bars[:-1], windows["ATR_PERIOD"])
    if atr <= 0.0:
        return _wait("ATR is zero")
    vwap, weighted_std = _session_vwap(session)
    scale = max(weighted_std, atr * float(c["VWAP_STD_FLOOR_ATR"]))
    last = bars[-1]
    zscore = (last["close"] - vwap) / scale

    divergence_n = windows["DIVERGENCE_BARS"]
    current = bars[-divergence_n:]
    previous = bars[-2 * divergence_n:-divergence_n]
    current_delta = _normalised_delta(current)
    previous_delta = _normalised_delta(previous)
    delta_change = current_delta - previous_delta
    previous_low = min(bar["low"] for bar in previous)
    previous_high = max(bar["high"] for bar in previous)
    current_low = min(bar["low"] for bar in current)
    current_high = max(bar["high"] for bar in current)

    candle_range = last["high"] - last["low"]
    if candle_range <= 0.0:
        return _wait("Latest candle has zero range")
    body = last["close"] - last["open"]
    close_location = (last["close"] - last["low"]) / candle_range
    lower_wick = min(last["open"], last["close"]) - last["low"]
    upper_wick = last["high"] - max(last["open"], last["close"])
    volume_window = bars[-max(20, divergence_n * 3):-1]
    baseline_volume = median(bar["tick_volume"] for bar in volume_window)
    if baseline_volume > 0.0 and last["tick_volume"] < baseline_volume * float(c["REJECTION_VOLUME_MULT"]):
        return _wait("Rejection volume is too low")

    extreme_buffer = atr * float(c["EXTREME_BREAK_ATR"])
    min_body = atr * float(c["REJECTION_BODY_ATR"])
    location = float(c["REJECTION_CLOSE_LOCATION"])
    wick_ratio = float(c["REJECTION_WICK_RATIO"])
    delta_min = float(c["DELTA_DIVERGENCE_MIN"])
    z_min = float(c["VWAP_Z_MIN"])

    direction = None
    if (
        zscore <= -z_min
        and current_low <= previous_low - extreme_buffer
        and delta_change >= delta_min
        and body >= min_body
        and close_location >= location
        and lower_wick / candle_range >= wick_ratio
    ):
        direction = "BUY"
    elif (
        zscore >= z_min
        and current_high >= previous_high + extreme_buffer
        and delta_change <= -delta_min
        and -body >= min_body
        and close_location <= 1.0 - location
        and upper_wick / candle_range >= wick_ratio
    ):
        direction = "SELL"
    if direction is None:
        return _wait("No VWAP extension + price/delta divergence rejection")

    fraction = float(c["ENTRY_RANGE_FRACTION"])
    if direction == "BUY":
        entry = last["low"] + fraction * candle_range
        sl = current_low - atr * float(c["SL_BUFFER_ATR"])
        risk = entry - sl
        if entry >= last["close"]:
            return _wait("BUY limit is not below signal close")
        minimum_target = entry + max(1.5, float(c["TP_RR"])) * risk
        if vwap < minimum_target:
            return _wait("VWAP target offers insufficient reward")
        tp = min(vwap, entry + float(c["TP_MAX_RR"]) * risk)
    else:
        entry = last["high"] - fraction * candle_range
        sl = current_high + atr * float(c["SL_BUFFER_ATR"])
        risk = sl - entry
        if entry <= last["close"]:
            return _wait("SELL limit is not above signal close")
        minimum_target = entry - max(1.5, float(c["TP_RR"])) * risk
        if vwap > minimum_target:
            return _wait("VWAP target offers insufficient reward")
        tp = max(vwap, entry - float(c["TP_MAX_RR"]) * risk)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Risk outside allowed range ({risk / atr:.2f} ATR)")

    allowed, probability = _ml_allows(c, rates, tf, direction, entry, dt_bkk)
    if not allowed:
        suffix = "unavailable" if probability is None else f"{probability:.2f}"
        return _wait(f"Blocked by ML ({suffix})")
    reason = (
        f"{direction} session VWAP z={zscore:.2f}; price made a new extreme "
        f"while normalized delta changed {delta_change:+.2f}; target VWAP={vwap:.2f}"
    )
    return _trade(direction, entry, sl, tp, c, reason)
