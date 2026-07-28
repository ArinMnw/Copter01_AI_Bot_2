# -*- coding: utf-8 -*-
"""S289 - Mood scale-contraction first directional release, 14.8R.

Unlike S146's RV/entropy range breakout, S289 uses Mood's distribution-free
rank statistic to identify return-scale contraction and requires only a strong
closed release candle. It enters at the next open with an event-extreme stop.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy288 import _mood_scale_z


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "MOOD_BASELINE_WINDOW": 48,
    "MOOD_RECENT_WINDOW": 16,
    "MOOD_Z_MAX": -1.025,
    "RELEASE_BODY_ATR_MIN": 0.925,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.65,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 14.80,
    "BE_RR": 1.825,
    "CANCEL_BARS": 3,
}


def detect_s289(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade the first controlled directional candle from scale contraction."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_window = max(8, int(c["MOOD_BASELINE_WINDOW"]))
        recent_window = max(4, int(c["MOOD_RECENT_WINDOW"]))
        z_max = float(c["MOOD_Z_MAX"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    history_returns = baseline_window + recent_window
    required = max(history_returns + 4, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [
            bar["close"]
            for bar in bars[-history_returns - 2:-1]
        ]
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
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
    zscore = _mood_scale_z(
        returns[:baseline_window],
        returns[baseline_window:],
    )
    if zscore is None:
        return _wait("Mood scale statistic is unavailable")
    if zscore > z_max:
        return _wait(f"Recent return scale is not contracted (z={zscore:.2f})")

    event = bars[-1]
    event_body = event["close"] - event["open"]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Release candle has zero range")
    if abs(event_body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if event_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    if event_body > 0.0:
        signal, side = "BUY", 1
        close_location = (event["close"] - event["low"]) / event_range
    elif event_body < 0.0:
        signal, side = "SELL", -1
        close_location = (event["high"] - event["close"]) / event_range
    else:
        return _wait("Release candle has no direction")
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
        "pattern": f"S289 {signal} Mood Contraction Release {rr:g}R",
        "reason": (
            f"Controlled directional release from rank-scale contraction "
            f"(z={zscore:.2f}, body={abs(event_body) / atr:.2f} ATR)"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
