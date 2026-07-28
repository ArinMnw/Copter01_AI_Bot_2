# -*- coding: utf-8 -*-
"""S157 - Robust first-jump exhaustion fade with a wick-defined short stop."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_WINDOW": 80,
    "JUMP_SIGMA_MIN": 3.00,
    "NO_PRIOR_JUMP_BARS": 8,
    "CLOSE_LOCATION_MIN": 0.75,
    "VOLUME_QUANTILE": 0.80,
    "MIN_WICK_ATR": 0.03,
    "ENTRY_WICK_FRACTION": 0.50,
    "SL_EXTREME_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 0.55,
    "MAX_RISK_PRICE_PCT": 0.18,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 2,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s157(rates, tf, dt_bkk, cfg):
    """Fade an isolated high-volume return jump from its terminal wick."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        baseline = max(40, int(c["BASELINE_WINDOW"]))
        prior_bars = max(1, int(c["NO_PRIOR_JUMP_BARS"]))
        period = max(1, int(c["ATR_PERIOD"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < baseline + prior_bars + period + 3 or dt_bkk is None:
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
    reference = returns[-baseline - prior_bars - 1:-prior_bars - 1]
    median_return = _quantile(reference, 0.50)
    mad = _quantile([abs(value - median_return) for value in reference], 0.50)
    robust_sigma = max(1e-12, mad * 1.4826)
    latest_return = returns[-1]
    jump_z = abs(latest_return - median_return) / robust_sigma
    threshold = float(c["JUMP_SIGMA_MIN"])
    if jump_z < threshold:
        return _wait("Latest return is not a robust jump")
    prior = returns[-prior_bars - 1:-1]
    if any(abs(value - median_return) / robust_sigma >= threshold for value in prior):
        return _wait("Jump is not isolated")

    latest = bars[-1]
    candle_range = latest["high"] - latest["low"]
    if candle_range <= 0.0:
        return _wait("Jump candle range is zero")
    history = bars[-baseline - 1:-1]
    volume_min = _quantile([bar["tick_volume"] for bar in history], c["VOLUME_QUANTILE"])
    if latest["tick_volume"] < volume_min:
        return _wait("Jump volume is below empirical threshold")

    body = latest["close"] - latest["open"]
    close_location = (latest["close"] - latest["low"]) / candle_range
    location_min = float(c["CLOSE_LOCATION_MIN"])
    wick_fraction = float(c["ENTRY_WICK_FRACTION"])
    if body > 0.0 and close_location >= location_min:
        direction = "SELL"
        wick = latest["high"] - latest["close"]
        entry = latest["close"] + wick * wick_fraction
        sl = latest["high"] + atr * float(c["SL_EXTREME_BUFFER_ATR"])
    elif body < 0.0 and close_location <= 1.0 - location_min:
        direction = "BUY"
        wick = latest["close"] - latest["low"]
        entry = latest["close"] - wick * wick_fraction
        sl = latest["low"] - atr * float(c["SL_EXTREME_BUFFER_ATR"])
    else:
        return _wait("Jump candle did not close near its directional extreme")
    if wick < atr * float(c["MIN_WICK_ATR"]):
        return _wait("Terminal wick is too small to define a fade")

    entry = round(entry, 2)
    sl = (math.ceil((sl - 1e-12) * 100) / 100 if direction == "SELL"
          else math.floor((sl + 1e-12) * 100) / 100)
    risk = sl - entry if direction == "SELL" else entry - sl
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Exhaustion-fade risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Exhaustion-fade risk too large versus price ({risk_pct:.2f}%)")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry - rr * risk if direction == "SELL" else entry + rr * risk
    tp = (math.floor((raw_tp + 1e-12) * 100) / 100 if direction == "SELL"
          else math.ceil((raw_tp - 1e-12) * 100) / 100)
    return {
        "signal": direction,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S157 {direction} Robust Jump Fade {rr:g}R",
        "reason": (f"Isolated robust jump z={jump_z:.2f}, volume>q{c['VOLUME_QUANTILE']}; "
                   f"fade from terminal wick {wick / atr:.2f}ATR"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
