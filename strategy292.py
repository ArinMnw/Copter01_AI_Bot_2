# -*- coding: utf-8 -*-
"""S292 - Ljung-Box multi-lag persistence release, 52.5R.

The Ljung-Box portmanteau statistic tests whether several return
autocorrelations are jointly different from zero.  S292 additionally requires
their weighted average to be positive, a directional displacement, and a
strong closed release candle before entering at the next open.  This is a
multi-lag magnitude-dependence regime, unlike S171's single lag-1 filter and
the distribution-shift family in S290/S291.
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
    "LJUNG_BOX_LAGS": 5,
    "LJUNG_BOX_Z_MIN": 0.30,
    "WEIGHTED_AUTOCORR_MIN": 0.00,
    "DIRECTION_WINDOW": 12,
    "DIRECTION_DISPLACEMENT_ATR_MIN": 0.45,
    "RELEASE_BODY_ATR_MIN": 0.55,
    "RELEASE_RANGE_ATR_MIN": 0.75,
    "RELEASE_CLOSE_FRACTION": 0.62,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    "TP_RR": 52.50,
    "BE_RR": 0.475,
    "CANCEL_BARS": 3,
}


def _ljung_box_persistence(values, lags):
    """Return (Q, Wilson-Hilferty z, weighted rho) or None."""
    n = len(values)
    if lags < 1 or n <= lags + 2:
        return None
    if any(not math.isfinite(float(value)) for value in values):
        return None
    mean = sum(values) / n
    centered = [value - mean for value in values]
    denominator = sum(value * value for value in centered)
    if denominator <= 0.0:
        return None
    correlations = []
    q_stat = 0.0
    for lag in range(1, lags + 1):
        numerator = sum(
            centered[index] * centered[index - lag]
            for index in range(lag, n)
        )
        rho = numerator / denominator
        correlations.append(rho)
        q_stat += rho * rho / (n - lag)
    q_stat *= n * (n + 2)
    degrees = float(lags)
    if q_stat <= 0.0:
        zscore = -math.inf
    else:
        # Wilson-Hilferty normal approximation to chi-square(df=lags).
        transformed = (q_stat / degrees) ** (1.0 / 3.0)
        center = 1.0 - 2.0 / (9.0 * degrees)
        scale = math.sqrt(2.0 / (9.0 * degrees))
        zscore = (transformed - center) / scale
    weights = [lags + 1 - lag for lag in range(1, lags + 1)]
    weighted_rho = sum(
        weight * rho for weight, rho in zip(weights, correlations)
    ) / sum(weights)
    return q_stat, zscore, weighted_rho


def detect_s292(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a controlled release in a significant persistence regime."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        return_lookback = max(16, int(c["RETURN_LOOKBACK"]))
        lags = max(1, int(c["LJUNG_BOX_LAGS"]))
        direction_window = max(2, int(c["DIRECTION_WINDOW"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(return_lookback + 4, direction_window + 4, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [bar["close"] for bar in bars[-return_lookback - 2:-1]]
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
        persistence = _ljung_box_persistence(returns, lags)
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
    if persistence is None:
        return _wait("Ljung-Box persistence statistic is unavailable")
    q_stat, zscore, weighted_rho = persistence
    if zscore < float(c["LJUNG_BOX_Z_MIN"]):
        return _wait(f"Serial dependence is insignificant (z={zscore:.2f})")
    if weighted_rho < float(c["WEIGHTED_AUTOCORR_MIN"]):
        return _wait(f"Multi-lag dependence is not persistent ({weighted_rho:.3f})")

    displacement = (
        bars[-2]["close"] - bars[-direction_window - 2]["close"]
    )
    if abs(displacement) < atr * float(c["DIRECTION_DISPLACEMENT_ATR_MIN"]):
        return _wait("Persistent regime lacks directional displacement")
    regime_side = 1 if displacement > 0.0 else -1
    event = bars[-1]
    event_body = event["close"] - event["open"]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Release candle has zero range")
    if event_body * regime_side <= 0.0:
        return _wait("Release candle opposes the persistent displacement")
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
        "pattern": f"S292 {signal} Ljung-Box Persistence {rr:g}R",
        "reason": (
            f"Multi-lag persistence Q={q_stat:.2f}, z={zscore:.2f}, "
            f"weighted rho={weighted_rho:.3f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
