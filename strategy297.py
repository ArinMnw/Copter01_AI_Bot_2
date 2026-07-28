# -*- coding: utf-8 -*-
"""S297 - Jarque-Bera asymmetric-tail release, SELL 52.5R.

The Jarque-Bera statistic jointly measures return skewness and excess
kurtosis.  S297 trades only when closed-bar returns are materially
non-Gaussian, the skew identifies a dominant tail, and the current closed
release candle confirms that tail direction.  This differs from earlier
single-skew strategies by requiring omnibus distribution-shape evidence.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "RETURN_LOOKBACK": 68,
    "JARQUE_BERA_MIN": 28.0,
    "ABS_SKEW_MIN": 0.40,
    "RELEASE_BODY_ATR_MIN": 0.55,
    "RELEASE_RANGE_ATR_MIN": 0.75,
    "RELEASE_CLOSE_FRACTION": 0.62,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    "TP_RR": 52.5,
    "BE_RR": 0.2875,
    "CANCEL_BARS": 3,
}


def _jarque_bera_shape(values):
    """Return (JB, skewness, excess kurtosis) using population moments."""
    n = len(values)
    if n < 8:
        return None
    try:
        xs = [float(value) for value in values]
    except (TypeError, ValueError, OverflowError):
        return None
    if any(not math.isfinite(value) for value in xs):
        return None
    mean = sum(xs) / n
    centered = [value - mean for value in xs]
    second = sum(value ** 2 for value in centered) / n
    if second <= 0.0:
        return None
    scale = math.sqrt(second)
    skewness = sum((value / scale) ** 3 for value in centered) / n
    kurtosis = sum((value / scale) ** 4 for value in centered) / n
    excess_kurtosis = kurtosis - 3.0
    jb_stat = n / 6.0 * (
        skewness ** 2 + 0.25 * excess_kurtosis ** 2
    )
    return jb_stat, skewness, excess_kurtosis


def detect_s297(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a controlled release in an asymmetric non-Gaussian regime."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        return_lookback = max(8, int(c["RETURN_LOOKBACK"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(return_lookback + 4, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [
            bar["close"] for bar in bars[-return_lookback - 2:-1]
        ]
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
        shape = _jarque_bera_shape(returns)
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
    if shape is None:
        return _wait("Jarque-Bera shape statistic is unavailable")
    jb_stat, skewness, excess_kurtosis = shape
    if jb_stat < float(c["JARQUE_BERA_MIN"]):
        return _wait(f"Return shape is not non-Gaussian (JB={jb_stat:.2f})")
    if abs(skewness) < float(c["ABS_SKEW_MIN"]):
        return _wait(f"Non-Gaussian regime lacks tail direction ({skewness:.2f})")

    regime_side = 1 if skewness > 0.0 else -1
    event = bars[-1]
    event_body = event["close"] - event["open"]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Release candle has zero range")
    if event_body * regime_side <= 0.0:
        return _wait("Release candle opposes the asymmetric tail")
    if abs(event_body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if event_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    if regime_side > 0:
        signal, side = "BUY", 1
        close_location = (event["close"] - event["low"]) / event_range
    else:
        signal, side = "SELL", -1
        close_location = (event["high"] - event["close"]) / event_range
    if close_location < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Release candle closes without tail-direction control")
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled by direction-survival filter")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled by direction-survival filter")

    entry = round(event["close"], 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor((event["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Release risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Release risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    if side > 0:
        tp = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
    else:
        tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S297 {signal} Jarque-Bera Tail {rr:g}R",
        "reason": (
            f"Non-Gaussian returns JB={jb_stat:.2f}, skew={skewness:.3f}, "
            f"excess kurtosis={excess_kurtosis:.2f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
