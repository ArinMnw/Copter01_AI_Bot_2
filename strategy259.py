# -*- coding: utf-8 -*-
"""S259 - Bipower-variation jump-exhaustion fade, 10R.

Realized bipower variation estimates the continuous component of short-horizon
price variance.  S259 fades only a fresh return jump relative to that estimate
when price sweeps local structure but the event candle closes away from its
extreme, indicating that the jump met opposing liquidity.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy232 import DEFAULT_CFG as S232_DEFAULT_CFG


DEFAULT_CFG = {
    **S232_DEFAULT_CFG,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "BV_LOOKBACK": 48,
    "JUMP_Z_MIN": 2.50,
    "SWEEP_LOOKBACK": 8,
    "REJECTION_WICK_MIN": 0.20,
    "CLOSE_LOCATION_MAX": 0.72,
    "VOLUME_RATIO_MIN": 1.00,
    "VOLUME_LOOKBACK": 24,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def _continuous_variance(returns):
    """Return per-bar bipower variation for a completed return sequence."""
    if len(returns) < 3:
        return 0.0
    products = [
        abs(returns[index - 1]) * abs(returns[index])
        for index in range(1, len(returns))
    ]
    return (math.pi / 2.0) * sum(products) / len(products)


def detect_s259(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a fresh non-continuous return jump after structural rejection."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(12, int(c["BV_LOOKBACK"]))
        sweep_lookback = max(2, int(c["SWEEP_LOOKBACK"]))
        volume_lookback = max(3, int(c["VOLUME_LOOKBACK"]))
        period = max(1, int(c["ATR_PERIOD"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(
        lookback + 3,
        sweep_lookback + 2,
        volume_lookback + 2,
        period + 5,
    )
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")

    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [bar["close"] for bar in bars[-lookback - 2:]]
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

    previous_variance = _continuous_variance(returns[-lookback - 1:-1])
    current_variance = _continuous_variance(returns[-lookback:])
    if min(previous_variance, current_variance) <= 0.0:
        return _wait("Bipower variation is zero")
    previous_jump_z = abs(returns[-2]) / math.sqrt(previous_variance)
    current_jump_z = abs(returns[-1]) / math.sqrt(current_variance)
    threshold = float(c["JUMP_Z_MIN"])
    if previous_jump_z >= threshold or current_jump_z < threshold:
        return _wait(
            f"No fresh bipower jump "
            f"(prev={previous_jump_z:.2f}, current={current_jump_z:.2f})"
        )

    event = bars[-1]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Event candle has zero range")
    close_location = (event["close"] - event["low"]) / event_range
    upper_wick = event["high"] - max(event["open"], event["close"])
    lower_wick = min(event["open"], event["close"]) - event["low"]
    prior = bars[-sweep_lookback - 1:-1]
    prior_high = max(bar["high"] for bar in prior)
    prior_low = min(bar["low"] for bar in prior)

    volumes = [
        max(0.0, float(bar.get("tick_volume", 0.0)))
        for bar in bars[-volume_lookback - 1:-1]
    ]
    median_volume = statistics.median(volumes)
    volume_ratio = (
        max(0.0, float(event.get("tick_volume", 0.0))) / median_volume
        if median_volume > 0.0
        else 0.0
    )
    if volume_ratio < float(c["VOLUME_RATIO_MIN"]):
        return _wait(f"Jump lacks participation ({volume_ratio:.2f}x)")

    wick_min = float(c["REJECTION_WICK_MIN"])
    close_limit = float(c["CLOSE_LOCATION_MAX"])
    current_return = returns[-1]
    if (
        current_return > 0.0
        and event["high"] > prior_high
        and upper_wick / event_range >= wick_min
        and close_location <= close_limit
    ):
        signal, side = "SELL", -1
    elif (
        current_return < 0.0
        and event["low"] < prior_low
        and lower_wick / event_range >= wick_min
        and close_location >= 1.0 - close_limit
    ):
        signal, side = "BUY", 1
    else:
        return _wait("Fresh jump lacks structural exhaustion rejection")

    entry = round(event["close"], 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor((event["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + buffer - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Fade risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Fade risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Fade risk too large versus price")

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
        "pattern": f"S259 {signal} Bipower Jump Exhaustion Fade {rr:g}R",
        "reason": (
            f"Fade fresh bipower jump z={current_jump_z:.2f}, "
            f"volume={volume_ratio:.2f}x, CLV={close_location:.2f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
