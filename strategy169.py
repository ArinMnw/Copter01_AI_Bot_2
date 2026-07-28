# -*- coding: utf-8 -*-
"""S169 - Volatility-compression bearish expansion retrace with a 7R target."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_WINDOW": 48,
    "COMPRESSION_WINDOW": 8,
    "COMPRESSION_RATIO_MAX": 0.72,
    "BREAKOUT_LOOKBACK": 18,
    "BREAKOUT_BODY_MIN_ATR": 0.70,
    "BREAKOUT_CLOSE_LOCATION_MAX": 0.28,
    "BREAKOUT_VOLUME_QUANTILE": 0.75,
    "ENTRY_BODY_FRACTION": 0.45,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.20,
    "MAX_RISK_PRICE_PCT": 0.30,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 5,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s169(rates, tf, dt_bkk, cfg):
    """Sell the retrace of a closed bearish expansion out of volatility compression."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_window = max(24, int(c["BASELINE_WINDOW"]))
        compression_window = max(4, int(c["COMPRESSION_WINDOW"]))
        breakout_lookback = max(6, int(c["BREAKOUT_LOOKBACK"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(baseline_window, breakout_lookback) + period + 3
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    pre_breakout = bars[:-1]
    true_ranges = []
    for index in range(1, len(pre_breakout)):
        bar = pre_breakout[index]
        prev_close = pre_breakout[index - 1]["close"]
        true_ranges.append(max(bar["high"] - bar["low"],
                               abs(bar["high"] - prev_close),
                               abs(bar["low"] - prev_close)))
    baseline = _quantile(true_ranges[-baseline_window:], 0.50)
    compressed = _quantile(true_ranges[-compression_window:], 0.50)
    compression_ratio = compressed / max(baseline, 1e-12)
    if compression_ratio > float(c["COMPRESSION_RATIO_MAX"]):
        return _wait(f"Volatility is not compressed ({compression_ratio:.2f})")

    breakout = bars[-1]
    breakout_range = breakout["high"] - breakout["low"]
    breakout_body = breakout["open"] - breakout["close"]
    if breakout_range <= 0.0 or breakout_body < atr * float(c["BREAKOUT_BODY_MIN_ATR"]):
        return _wait("No bearish range expansion")
    close_location = (breakout["close"] - breakout["low"]) / breakout_range
    prior_low = min(bar["low"] for bar in bars[-breakout_lookback - 1:-1])
    if (breakout["close"] >= prior_low
            or close_location > float(c["BREAKOUT_CLOSE_LOCATION_MAX"])):
        return _wait("Expansion did not close below prior structure")
    volume_min = _quantile(
        [bar["tick_volume"] for bar in bars[-baseline_window - 1:-1]],
        c["BREAKOUT_VOLUME_QUANTILE"],
    )
    if breakout["tick_volume"] < volume_min:
        return _wait("Breakout volume is below empirical threshold")

    fraction = float(c["ENTRY_BODY_FRACTION"])
    entry = breakout["close"] + fraction * breakout_body
    if entry <= breakout["close"]:
        return _wait("SELL limit is not above breakout close")
    sl = breakout["high"] + atr * float(c["SL_BUFFER_ATR"])
    entry = round(entry, 2)
    sl = math.ceil((sl - 1e-12) * 100.0) / 100.0
    risk = sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Compression-breakout risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Compression-breakout risk too large versus price ({risk_pct:.2f}%)")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry - rr * risk
    tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": "SELL",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S169 SELL Compression Expansion {rr:g}R",
        "reason": (f"Compression={compression_ratio:.2f}; bearish expansion closed below "
                   f"{breakout_lookback}-bar structure on high volume"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
