# -*- coding: utf-8 -*-
"""S119 — Volatility Term-Structure Expansion Continuation.

Detect the first transition from quiet long-horizon realized volatility to a
coherent short-horizon expansion.  Unlike S118 it does not use price levels or
auction acceptance; direction comes from normalized return efficiency and
entry is a limit retrace into the latest expansion candle.
"""

from __future__ import annotations

import math
from statistics import median


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SHORT_WINDOW": 6,
    "LONG_WINDOW": 48,
    "RV_EXPANSION_MIN": 1.45,
    "PREVIOUS_RV_MAX": 1.10,
    "MOVE_MIN_ATR": 1.00,
    "EFFICIENCY_MIN": 0.62,
    "VOLUME_EXPANSION_MIN": 1.00,
    "TIME_FILTER_ENABLED": True,
    "TRADE_HOURS": tuple(range(7, 24)),
    "ENTRY_CANDLE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.30,
    "MAX_RISK_ATR": 4.00,
    "TP_RR": 1.80,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
    "ML_FILTER_ENABLED": False,
    "ML_SCORE_THRESHOLD": 0.55,
    "ML_SYMBOL": "XAUUSD.iux",
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("non-finite value")
    return value


def _bars(rates):
    output, previous = [], None
    for raw in rates:
        timestamp = int(_finite(raw["time"]))
        if previous is not None and timestamp <= previous:
            raise ValueError("rates are not chronological")
        previous = timestamp
        bar = {"time": timestamp, "open": _finite(raw["open"]),
               "high": _finite(raw["high"]), "low": _finite(raw["low"]),
               "close": _finite(raw["close"]),
               "tick_volume": max(0.0, _finite(raw["tick_volume"]))}
        if bar["high"] < max(bar["open"], bar["close"], bar["low"]):
            raise ValueError("invalid high")
        if bar["low"] > min(bar["open"], bar["close"], bar["high"]):
            raise ValueError("invalid low")
        output.append(bar)
    return output


def _atr(bars, period):
    if len(bars) < period + 1:
        return 0.0
    values = []
    for index in range(len(bars) - period, len(bars)):
        bar, previous = bars[index], bars[index - 1]["close"]
        values.append(max(bar["high"] - bar["low"],
                          abs(bar["high"] - previous), abs(bar["low"] - previous)))
    return sum(values) / len(values)


def _rms(values):
    return math.sqrt(sum(value * value for value in values) / len(values)) if values else 0.0


def _ml_ok(cfg, rates, tf, direction, entry, dt_bkk):
    if not cfg["ML_FILTER_ENABLED"]:
        return True, None
    try:
        import ml_scoring
        probability = float(ml_scoring.score_signal(
            cfg["ML_SYMBOL"], tf, direction, entry, dt_bkk,
            historical_rates=rates))
    except Exception:
        return False, None
    return probability >= float(cfg["ML_SCORE_THRESHOLD"]), probability


def _trade(direction, entry, sl, cfg, reason):
    entry, sl = round(entry, 2), round(sl, 2)
    risk = entry - sl if direction == "BUY" else sl - entry
    if risk <= 0.0:
        return _wait("Invalid rounded risk")
    rr = max(1.5, float(cfg["TP_RR"]))
    raw = entry + rr * risk if direction == "BUY" else entry - rr * risk
    tp = (math.ceil((raw - 1e-12) * 100) / 100 if direction == "BUY"
          else math.floor((raw + 1e-12) * 100) / 100)
    return {"signal": direction, "entry": entry, "sl": sl, "tp": tp,
            "order_type": "limit", "pattern": f"S119 {direction} RV Expansion",
            "reason": reason, "be_rr": float(cfg["BE_RR"]),
            "cancel_bars": int(cfg["CANCEL_BARS"])}


def detect_s119(rates, tf, dt_bkk, cfg):
    """Return the first closed-bar realized-volatility expansion signal."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        short, long, period = int(c["SHORT_WINDOW"]), int(c["LONG_WINDOW"]), int(c["ATR_PERIOD"])
        if short < 3 or long < short * 3 or period < 1:
            return _wait("Invalid windows")
    except (KeyError, TypeError, ValueError, OverflowError):
        return _wait("Invalid cfg")
    required = long + short * 2 + 2
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or no dt_bkk")
    try:
        if c["TIME_FILTER_ENABLED"] and dt_bkk.hour not in tuple(c["TRADE_HOURS"]):
            return _wait("Outside trade hours")
        bars = _bars(rates)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid input: {exc}")
    atr = _atr(bars[:-1], period)
    if atr <= 0.0:
        return _wait("ATR is zero")
    returns = [bars[index]["close"] - bars[index - 1]["close"]
               for index in range(1, len(bars))]
    current = returns[-short:]
    previous = returns[-2 * short:-short]
    baseline = returns[-2 * short - long:-2 * short]
    long_rv = _rms(baseline)
    if long_rv <= 0.0:
        return _wait("Long realized volatility is zero")
    current_ratio, previous_ratio = _rms(current) / long_rv, _rms(previous) / long_rv
    if current_ratio < float(c["RV_EXPANSION_MIN"]) or previous_ratio > float(c["PREVIOUS_RV_MAX"]):
        return _wait("No first volatility term-structure expansion")
    move, path = sum(current), sum(abs(value) for value in current)
    efficiency = abs(move) / path if path > 0.0 else 0.0
    if abs(move) < atr * float(c["MOVE_MIN_ATR"]) or efficiency < float(c["EFFICIENCY_MIN"]):
        return _wait("Expansion lacks directional efficiency")
    direction = "BUY" if move > 0.0 else "SELL"
    volume_base = median(bar["tick_volume"] for bar in bars[-long - short:-short])
    volume_now = sum(bar["tick_volume"] for bar in bars[-short:]) / short
    volume_ratio = volume_now / volume_base if volume_base > 0.0 else 0.0
    if volume_ratio < float(c["VOLUME_EXPANSION_MIN"]):
        return _wait("Expansion lacks volume")
    last = bars[-1]
    fraction = float(c["ENTRY_CANDLE_FRACTION"])
    entry = last["low"] + fraction * (last["high"] - last["low"])
    if direction == "BUY":
        if last["close"] <= last["open"] or entry >= last["close"]:
            return _wait("Latest candle does not confirm BUY")
        sl = min(bar["low"] for bar in bars[-short:]) - atr * float(c["SL_BUFFER_ATR"])
        risk = entry - sl
    else:
        if last["close"] >= last["open"] or entry <= last["close"]:
            return _wait("Latest candle does not confirm SELL")
        sl = max(bar["high"] for bar in bars[-short:]) + atr * float(c["SL_BUFFER_ATR"])
        risk = sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Risk outside range ({risk / atr:.2f} ATR)")
    allowed, probability = _ml_ok(c, rates, tf, direction, entry, dt_bkk)
    if not allowed:
        suffix = "unavailable" if probability is None else f"{probability:.2f}"
        return _wait(f"Blocked by ML ({suffix})")
    reason = (f"{direction} short/long RV={current_ratio:.2f}, previous={previous_ratio:.2f}, "
              f"efficiency={efficiency:.2f}, volume={volume_ratio:.2f}x")
    return _trade(direction, entry, sl, c, reason)
