# -*- coding: utf-8 -*-
"""S120 — Volatility Expansion Exhaustion Fade.

S119 showed that coherent volatility expansion continuation failed.  S120
tests the falsifiable opposite case: a large short/long realized-volatility
ratio whose multi-bar path is inefficient, followed by a closed reversal
candle.  The natural target is the pre-expansion mean, subject to >=1.5R.
"""

from __future__ import annotations

import math
from statistics import median

from strategy119 import _atr, _bars, _rms, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14, "SHORT_WINDOW": 8, "LONG_WINDOW": 48,
    "RV_EXPANSION_MIN": 1.55, "PREVIOUS_RV_MAX": 1.20,
    "IMPULSE_MIN_ATR": 1.00, "EFFICIENCY_MAX": 0.50,
    "REVERSAL_BODY_ATR": 0.12, "VOLUME_MULT": 1.00,
    "TIME_FILTER_ENABLED": True, "TRADE_HOURS": tuple(range(7, 24)),
    "ENTRY_CANDLE_FRACTION": 0.50, "SL_BUFFER_ATR": 0.25,
    "MAX_RISK_ATR": 3.50, "TP_RR": 1.60, "TP_MAX_RR": 2.50,
    "BE_RR": 1.00, "CANCEL_BARS": 3,
}


def _trade(direction, entry, sl, tp, cfg, reason):
    entry, sl = round(entry, 2), round(sl, 2)
    risk = entry - sl if direction == "BUY" else sl - entry
    if risk <= 0.0:
        return _wait("Invalid rounded risk")
    minimum = max(1.5, float(cfg["TP_RR"]))
    if direction == "BUY":
        tp = max(tp, entry + minimum * risk)
        tp = math.ceil((tp - 1e-12) * 100) / 100
    else:
        tp = min(tp, entry - minimum * risk)
        tp = math.floor((tp + 1e-12) * 100) / 100
    return {"signal": direction, "entry": entry, "sl": sl, "tp": tp,
            "order_type": "limit", "pattern": f"S120 {direction} RV Exhaustion",
            "reason": reason, "be_rr": float(cfg["BE_RR"]),
            "cancel_bars": int(cfg["CANCEL_BARS"])}


def detect_s120(rates, tf, dt_bkk, cfg):
    """Detect an inefficient volatility-expansion reversal on closed bars."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        short, long, period = int(c["SHORT_WINDOW"]), int(c["LONG_WINDOW"]), int(c["ATR_PERIOD"])
        if short < 4 or long < short * 3 or period < 1:
            return _wait("Invalid windows")
    except (KeyError, TypeError, ValueError, OverflowError):
        return _wait("Invalid cfg")
    if rates is None or len(rates) < long + short * 2 + 2 or dt_bkk is None:
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
    current, previous = returns[-short:], returns[-2 * short:-short]
    baseline = returns[-2 * short - long:-2 * short]
    long_rv = _rms(baseline)
    if long_rv <= 0.0:
        return _wait("Long RV is zero")
    current_ratio, previous_ratio = _rms(current) / long_rv, _rms(previous) / long_rv
    if current_ratio < float(c["RV_EXPANSION_MIN"]) or previous_ratio > float(c["PREVIOUS_RV_MAX"]):
        return _wait("No first volatility expansion")
    impulse = sum(current[:-1])
    path = sum(abs(value) for value in current)
    efficiency = abs(sum(current)) / path if path > 0.0 else 1.0
    if abs(impulse) < atr * float(c["IMPULSE_MIN_ATR"]) or efficiency > float(c["EFFICIENCY_MAX"]):
        return _wait("Expansion is not inefficient exhaustion")
    last = bars[-1]
    body = last["close"] - last["open"]
    direction = "SELL" if impulse > 0.0 else "BUY"
    if ((direction == "SELL" and body > -atr * float(c["REVERSAL_BODY_ATR"]))
            or (direction == "BUY" and body < atr * float(c["REVERSAL_BODY_ATR"]))):
        return _wait("No closed reversal candle")
    baseline_volume = median(bar["tick_volume"] for bar in bars[-long - short:-short])
    if baseline_volume > 0.0 and last["tick_volume"] < baseline_volume * float(c["VOLUME_MULT"]):
        return _wait("Reversal volume too low")
    candle_range = last["high"] - last["low"]
    entry = last["low"] + float(c["ENTRY_CANDLE_FRACTION"]) * candle_range
    pre_mean = sum(bar["close"] for bar in bars[-short - long:-short]) / long
    if direction == "BUY":
        if entry >= last["close"]:
            return _wait("BUY limit is not below close")
        sl = min(bar["low"] for bar in bars[-short:]) - atr * float(c["SL_BUFFER_ATR"])
        risk = entry - sl
        if pre_mean < entry + max(1.5, float(c["TP_RR"])) * risk:
            return _wait("Mean target has insufficient RR")
        tp = min(pre_mean, entry + float(c["TP_MAX_RR"]) * risk)
    else:
        if entry <= last["close"]:
            return _wait("SELL limit is not above close")
        sl = max(bar["high"] for bar in bars[-short:]) + atr * float(c["SL_BUFFER_ATR"])
        risk = sl - entry
        if pre_mean > entry - max(1.5, float(c["TP_RR"])) * risk:
            return _wait("Mean target has insufficient RR")
        tp = max(pre_mean, entry - float(c["TP_MAX_RR"]) * risk)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Risk outside range ({risk / atr:.2f} ATR)")
    reason = (f"{direction} fade RV={current_ratio:.2f}, previous={previous_ratio:.2f}, "
              f"efficiency={efficiency:.2f}, target mean={pre_mean:.2f}")
    return _trade(direction, entry, sl, tp, c, reason)
