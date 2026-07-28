# -*- coding: utf-8 -*-
"""S152 — Realized-return skewness tail snapback with a short 7R stop."""

from __future__ import annotations

import math
from statistics import median

from strategy119 import _atr, _bars


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SKEW_WINDOW": 48,
    "TAIL_WINDOW": 8,
    "SKEW_ABS_MIN": 1.40,
    "TAIL_MOVE_MIN_ATR": 1.00,
    "REVERSAL_BODY_MIN_ATR": 0.18,
    "REVERSAL_VOLUME_MULT": 1.00,
    "ENTRY_CANDLE_FRACTION": 0.50,
    "SL_TAIL_BUFFER_ATR": 0.15,
    "MAX_RISK_ATR": 1.50,
    "MAX_RISK_PRICE_PCT": 0.40,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _skewness(values):
    if len(values) < 3:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    if variance <= 0.0:
        return 0.0
    scale = math.sqrt(variance)
    return sum(((value - mean) / scale) ** 3 for value in values) / len(values)


def detect_s152(rates, tf, dt_bkk, cfg):
    """Fade an extreme rolling skew tail after a closed opposite reversal."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        window = max(20, int(c["SKEW_WINDOW"]))
        tail = max(4, int(c["TAIL_WINDOW"]))
        period = max(1, int(c["ATR_PERIOD"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < window + tail + period + 3 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    returns = [bars[index]["close"] - bars[index - 1]["close"]
               for index in range(1, len(bars))]
    skew = _skewness(returns[-window:])
    tail_move = sum(returns[-tail:-1])
    latest = bars[-1]
    body = latest["close"] - latest["open"]
    if abs(skew) < float(c["SKEW_ABS_MIN"]):
        return _wait("Rolling return skew is not extreme")
    if abs(tail_move) < atr * float(c["TAIL_MOVE_MIN_ATR"]):
        return _wait("Recent tail move is too small")
    if skew > 0.0 and tail_move > 0.0 and body <= -atr * float(c["REVERSAL_BODY_MIN_ATR"]):
        direction = "SELL"
    elif skew < 0.0 and tail_move < 0.0 and body >= atr * float(c["REVERSAL_BODY_MIN_ATR"]):
        direction = "BUY"
    else:
        return _wait("No closed reversal against the skew tail")
    volume_base = median(bar["tick_volume"] for bar in bars[-window - 1:-1])
    if volume_base > 0.0 and latest["tick_volume"] < volume_base * float(c["REVERSAL_VOLUME_MULT"]):
        return _wait("Reversal volume is too low")
    fraction = float(c["ENTRY_CANDLE_FRACTION"])
    entry = latest["low"] + fraction * (latest["high"] - latest["low"])
    if direction == "SELL":
        if entry <= latest["close"]:
            return _wait("SELL limit is not above reversal close")
        sl = max(bar["high"] for bar in bars[-tail:]) + atr * float(c["SL_TAIL_BUFFER_ATR"])
        risk = sl - entry
    else:
        if entry >= latest["close"]:
            return _wait("BUY limit is not below reversal close")
        sl = min(bar["low"] for bar in bars[-tail:]) - atr * float(c["SL_TAIL_BUFFER_ATR"])
        risk = entry - sl
    entry = round(entry, 2)
    sl = (math.ceil((sl - 1e-12) * 100) / 100 if direction == "SELL"
          else math.floor((sl + 1e-12) * 100) / 100)
    risk = sl - entry if direction == "SELL" else entry - sl
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Skew-tail risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Skew-tail risk too large versus price ({risk_pct:.2f}%)")
    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry - rr * risk if direction == "SELL" else entry + rr * risk
    tp = (math.floor((raw_tp + 1e-12) * 100) / 100 if direction == "SELL"
          else math.ceil((raw_tp - 1e-12) * 100) / 100)
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "order_type": "limit", "pattern": f"S152 {direction} Skew Tail {rr:g}R",
        "reason": (f"Rolling skew={skew:+.2f}, tail move={tail_move / atr:+.2f}ATR; "
                   f"closed reversal confirmed"),
        "be_rr": float(c["BE_RR"]), "cancel_bars": int(c["CANCEL_BARS"]),
    }
