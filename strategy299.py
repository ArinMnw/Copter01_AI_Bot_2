# -*- coding: utf-8 -*-
"""S299 - Gini volatility-concentration directional release, SELL 52.5R.

The Gini coefficient measures how strongly absolute closed-bar returns are
concentrated in a small number of shocks.  S299 requires both high Gini
inequality and a dominant top-quartile share, then trades a controlled release
aligned with recent displacement.  This targets shock-cluster continuation
without reusing the Jarque-Bera shape or failed-sweep logic of S297/S298.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "RETURN_LOOKBACK": 64,
    "GINI_MIN": 0.47,
    "TOP_QUARTILE_SHARE_MIN": 0.57,
    "DIRECTION_WINDOW": 12,
    "DIRECTION_DISPLACEMENT_ATR_MIN": 0.45,
    "RELEASE_BODY_ATR_MIN": 0.60,
    "RELEASE_RANGE_ATR_MIN": 0.75,
    "RELEASE_CLOSE_FRACTION": 0.62,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    "TP_RR": 52.5,
    "BE_RR": 0.25,
    "CANCEL_BARS": 3,
}


def _gini_concentration(values):
    """Return (Gini coefficient, top-quartile share) for nonnegative values."""
    n = len(values)
    if n < 4:
        return None
    try:
        xs = [float(value) for value in values]
    except (TypeError, ValueError, OverflowError):
        return None
    if any(not math.isfinite(value) or value < 0.0 for value in xs):
        return None
    total = sum(xs)
    if total <= 0.0:
        return None
    ordered = sorted(xs)
    weighted_sum = sum(
        (2 * index - n - 1) * value
        for index, value in enumerate(ordered, start=1)
    )
    gini = weighted_sum / (n * total)
    top_count = max(1, math.ceil(n / 4.0))
    top_share = sum(ordered[-top_count:]) / total
    return max(0.0, min(1.0, gini)), top_share


def detect_s299(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow displacement only when realized movement is shock-concentrated."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        return_lookback = max(8, int(c["RETURN_LOOKBACK"]))
        direction_window = max(2, int(c["DIRECTION_WINDOW"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(
        return_lookback + 4,
        direction_window + 4,
        period + 5,
    )
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
        absolute_returns = [
            abs(math.log(closes[index] / closes[index - 1]))
            for index in range(1, len(closes))
        ]
        concentration = _gini_concentration(absolute_returns)
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
    if concentration is None:
        return _wait("Gini volatility concentration is unavailable")
    gini, top_share = concentration
    if gini < float(c["GINI_MIN"]):
        return _wait(f"Realized movement is too evenly distributed ({gini:.3f})")
    if top_share < float(c["TOP_QUARTILE_SHARE_MIN"]):
        return _wait(f"Top-quartile volatility share is too small ({top_share:.3f})")

    displacement = (
        bars[-2]["close"] - bars[-direction_window - 2]["close"]
    )
    if abs(displacement) < atr * float(c["DIRECTION_DISPLACEMENT_ATR_MIN"]):
        return _wait("Shock concentration lacks directional displacement")
    regime_side = 1 if displacement > 0.0 else -1
    event = bars[-1]
    event_body = event["close"] - event["open"]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Release candle has zero range")
    if event_body * regime_side <= 0.0:
        return _wait("Release candle opposes concentrated displacement")
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
        return _wait("Release candle closes without directional control")
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
        "pattern": f"S299 {signal} Gini Shock Release {rr:g}R",
        "reason": (
            f"Shock-concentrated movement Gini={gini:.6f}, "
            f"top-quartile share={top_share:.6f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
