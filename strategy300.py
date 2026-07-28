# -*- coding: utf-8 -*-
"""S300 - Anderson-Darling asymmetric-tail directional release, BUY 12R.

The Anderson-Darling statistic compares the full empirical return CDF with a
fitted normal distribution while heavily weighting both tails.  S300 combines
that tail-sensitive departure score with a signed extreme-tail energy
imbalance, then requires a closed directional release candle.  Unlike S297's
moment-based Jarque-Bera gate, a few observations far into either tail affect
this detector through their empirical tail probabilities rather than only
through skewness and kurtosis.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "RETURN_LOOKBACK": 62,
    "ANDERSON_DARLING_MIN": 1.45,
    "TAIL_FRACTION": 0.15,
    "TAIL_IMBALANCE_MIN": 0.145,
    "RELEASE_BODY_ATR_MIN": 0.55,
    "RELEASE_RANGE_ATR_MIN": 0.65,
    "RELEASE_CLOSE_FRACTION": 0.62,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": False,
    "TP_RR": 12.0,
    "BE_RR": 0.50,
    "CANCEL_BARS": 3,
}


def _normal_cdf(value):
    """Standard-normal CDF without a third-party dependency."""
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _anderson_darling_tail(values, tail_fraction):
    """Return corrected normal AD statistic and signed tail-energy imbalance."""
    n = len(values)
    if n < 12:
        return None
    try:
        xs = [float(value) for value in values]
        fraction = float(tail_fraction)
    except (TypeError, ValueError, OverflowError):
        return None
    if any(not math.isfinite(value) for value in xs):
        return None
    if not 0.05 <= fraction <= 0.45:
        return None
    mean = sum(xs) / n
    variance = sum((value - mean) ** 2 for value in xs) / n
    if variance <= 0.0:
        return None
    scale = math.sqrt(variance)
    standardized = sorted((value - mean) / scale for value in xs)
    epsilon = 1e-12
    probabilities = [
        min(1.0 - epsilon, max(epsilon, _normal_cdf(value)))
        for value in standardized
    ]
    weighted_logs = 0.0
    for index in range(1, n + 1):
        left = probabilities[index - 1]
        right = probabilities[n - index]
        weighted_logs += (2 * index - 1) * (
            math.log(left) + math.log(1.0 - right)
        )
    statistic = -n - weighted_logs / n
    corrected = statistic * (1.0 + 0.75 / n + 2.25 / (n * n))

    tail_count = max(1, math.ceil(n * fraction))
    lower_energy = sum(abs(value) for value in standardized[:tail_count])
    upper_energy = sum(abs(value) for value in standardized[-tail_count:])
    total_energy = lower_energy + upper_energy
    if total_energy <= 0.0:
        return None
    imbalance = (upper_energy - lower_energy) / total_energy
    return max(0.0, corrected), max(-1.0, min(1.0, imbalance))


def detect_s300(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a controlled release toward the dominant empirical return tail."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        return_lookback = max(12, int(c["RETURN_LOOKBACK"]))
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
        tail_shape = _anderson_darling_tail(
            returns,
            c["TAIL_FRACTION"],
        )
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
    if tail_shape is None:
        return _wait("Anderson-Darling tail statistic is unavailable")
    statistic, imbalance = tail_shape
    if statistic < float(c["ANDERSON_DARLING_MIN"]):
        return _wait(
            f"Return CDF lacks tail-sensitive departure (AD={statistic:.3f})"
        )
    if abs(imbalance) < float(c["TAIL_IMBALANCE_MIN"]):
        return _wait(
            f"Extreme-tail energy lacks direction ({imbalance:.3f})"
        )

    regime_side = 1 if imbalance > 0.0 else -1
    event = bars[-1]
    event_body = event["close"] - event["open"]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Release candle has zero range")
    if event_body * regime_side <= 0.0:
        return _wait("Release candle opposes the dominant empirical tail")
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
        "pattern": f"S300 {signal} Anderson-Darling Tail {rr:g}R",
        "reason": (
            f"Tail-sensitive return CDF AD={statistic:.6f}, "
            f"tail-energy imbalance={imbalance:.6f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
