# -*- coding: utf-8 -*-
"""S146 — Entropy-compression range release with a short 7R retest."""

from __future__ import annotations

import math
from statistics import median

from strategy119 import _atr, _bars, _rms


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "COMPRESSION_WINDOW": 12,
    "BASELINE_WINDOW": 64,
    "RV_RATIO_MAX": 0.65,
    "SIGN_ENTROPY_MIN": 0.85,
    "RANGE_MAX_ATR": 2.00,
    "BREAK_BUFFER_ATR": 0.05,
    "BREAK_BODY_MIN_ATR": 0.45,
    "VOLUME_EXPANSION_MIN": 1.35,
    "SL_BREAK_BUFFER_ATR": 0.10,
    "MAX_RISK_ATR": 1.25,
    "MAX_RISK_PRICE_PCT": 0.40,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _binary_entropy(returns):
    nonzero = [value for value in returns if value != 0.0]
    if not nonzero:
        return 0.0
    probability = sum(value > 0.0 for value in nonzero) / len(nonzero)
    if probability <= 0.0 or probability >= 1.0:
        return 0.0
    return -(probability * math.log2(probability)
             + (1.0 - probability) * math.log2(1.0 - probability))


def detect_s146(rates, tf, dt_bkk, cfg):
    """Detect a closed volume breakout from a high-entropy volatility squeeze."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        compression = max(6, int(c["COMPRESSION_WINDOW"]))
        baseline = max(compression * 3, int(c["BASELINE_WINDOW"]))
        period = max(1, int(c["ATR_PERIOD"]))
        required = baseline + compression + period + 4
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    squeeze = bars[-compression - 1:-1]
    base = bars[-compression - baseline - 1:-compression - 1]
    squeeze_returns = [squeeze[index]["close"] - squeeze[index - 1]["close"]
                       for index in range(1, len(squeeze))]
    base_returns = [base[index]["close"] - base[index - 1]["close"]
                    for index in range(1, len(base))]
    base_rv = _rms(base_returns)
    if base_rv <= 0.0:
        return _wait("Baseline realized volatility is zero")
    rv_ratio = _rms(squeeze_returns) / base_rv
    entropy = _binary_entropy(squeeze_returns)
    range_high = max(bar["high"] for bar in squeeze)
    range_low = min(bar["low"] for bar in squeeze)
    range_atr = (range_high - range_low) / atr
    if (rv_ratio > float(c["RV_RATIO_MAX"])
            or entropy < float(c["SIGN_ENTROPY_MIN"])
            or range_atr > float(c["RANGE_MAX_ATR"])):
        return _wait("No high-entropy volatility compression")

    latest = bars[-1]
    body = latest["close"] - latest["open"]
    volume_base = median(bar["tick_volume"] for bar in base)
    volume_ratio = latest["tick_volume"] / volume_base if volume_base > 0.0 else 0.0
    if (abs(body) < atr * float(c["BREAK_BODY_MIN_ATR"])
            or volume_ratio < float(c["VOLUME_EXPANSION_MIN"])):
        return _wait("Release candle lacks body or volume expansion")
    upper = range_high + atr * float(c["BREAK_BUFFER_ATR"])
    lower = range_low - atr * float(c["BREAK_BUFFER_ATR"])
    if latest["close"] > upper and body > 0.0:
        direction, entry = "BUY", round(range_high, 2)
        sl = math.floor((latest["low"] - atr * float(c["SL_BREAK_BUFFER_ATR"]) + 1e-12)
                        * 100) / 100
        risk = entry - sl
    elif latest["close"] < lower and body < 0.0:
        direction, entry = "SELL", round(range_low, 2)
        sl = math.ceil((latest["high"] + atr * float(c["SL_BREAK_BUFFER_ATR"]) - 1e-12)
                       * 100) / 100
        risk = sl - entry
    else:
        return _wait("Release candle did not close outside compression range")
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Breakout structure risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Breakout risk too large versus price ({risk_pct:.2f}%)")
    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + rr * risk if direction == "BUY" else entry - rr * risk
    tp = (math.ceil((raw_tp - 1e-12) * 100) / 100 if direction == "BUY"
          else math.floor((raw_tp + 1e-12) * 100) / 100)
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "order_type": "limit",
        "pattern": f"S146 {direction} Entropy Release {rr:g}R",
        "reason": (f"Compression RV={rv_ratio:.2f}, entropy={entropy:.2f}, "
                   f"range={range_atr:.2f}ATR, release volume={volume_ratio:.2f}x"),
        "be_rr": float(c["BE_RR"]), "cancel_bars": int(c["CANCEL_BARS"]),
    }
