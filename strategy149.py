# -*- coding: utf-8 -*-
"""S149 — Empirical extreme-range/volume wick rejection with a 7R target."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "LOOKBACK": 120,
    "RANGE_QUANTILE": 0.90,
    "VOLUME_QUANTILE": 0.80,
    "WICK_MIN_FRACTION": 0.50,
    "CLOSE_LOCATION_EXTREME": 0.25,
    "WICK_ENTRY_FRACTION": 0.50,
    "SL_EXTREME_BUFFER_ATR": 0.10,
    "MAX_RISK_ATR": 1.25,
    "MAX_RISK_PRICE_PCT": 0.40,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _quantile(values, probability):
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    probability = min(1.0, max(0.0, float(probability)))
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def detect_s149(rates, tf, dt_bkk, cfg):
    """Fade a statistically extreme effort candle that rejects its long wick."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(40, int(c["LOOKBACK"]))
        period = max(1, int(c["ATR_PERIOD"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < lookback + period + 2 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    history = bars[-lookback - 1:-1]
    ranges = [bar["high"] - bar["low"] for bar in history]
    range_threshold = _quantile(ranges, c["RANGE_QUANTILE"])
    volume_threshold = _quantile([bar["tick_volume"] for bar in history],
                                 c["VOLUME_QUANTILE"])
    latest = bars[-1]
    candle_range = latest["high"] - latest["low"]
    if (candle_range <= 0.0 or candle_range < range_threshold
            or latest["tick_volume"] < volume_threshold):
        return _wait("Latest effort candle is not empirically extreme")
    close_location = (latest["close"] - latest["low"]) / candle_range
    upper_wick = latest["high"] - max(latest["open"], latest["close"])
    lower_wick = min(latest["open"], latest["close"]) - latest["low"]
    wick_min = float(c["WICK_MIN_FRACTION"])
    extreme = float(c["CLOSE_LOCATION_EXTREME"])
    fraction = float(c["WICK_ENTRY_FRACTION"])
    if upper_wick / candle_range >= wick_min and close_location <= extreme:
        direction = "SELL"
        entry = latest["high"] - upper_wick * fraction
        sl = latest["high"] + atr * float(c["SL_EXTREME_BUFFER_ATR"])
    elif lower_wick / candle_range >= wick_min and close_location >= 1.0 - extreme:
        direction = "BUY"
        entry = latest["low"] + lower_wick * fraction
        sl = latest["low"] - atr * float(c["SL_EXTREME_BUFFER_ATR"])
    else:
        return _wait("Extreme effort candle did not reject a dominant wick")
    entry = round(entry, 2)
    sl = (math.ceil((sl - 1e-12) * 100) / 100 if direction == "SELL"
          else math.floor((sl + 1e-12) * 100) / 100)
    risk = sl - entry if direction == "SELL" else entry - sl
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Wick structure risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Wick risk too large versus price ({risk_pct:.2f}%)")
    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry - rr * risk if direction == "SELL" else entry + rr * risk
    tp = (math.floor((raw_tp + 1e-12) * 100) / 100 if direction == "SELL"
          else math.ceil((raw_tp - 1e-12) * 100) / 100)
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "order_type": "limit",
        "pattern": f"S149 {direction} Extreme Wick Rejection {rr:g}R",
        "reason": (f"Range={candle_range / atr:.2f}ATR above q{c['RANGE_QUANTILE']}; "
                   f"volume={latest['tick_volume']:.0f} above empirical threshold; "
                   f"close location={close_location:.2f}"),
        "be_rr": float(c["BE_RR"]), "cancel_bars": int(c["CANCEL_BARS"]),
    }
