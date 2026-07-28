# -*- coding: utf-8 -*-
"""S283 - High-turning-point failed-sweep reclaim, 10R.

For an independent continuous sequence, the expected number of local turning
points is 2(n-2)/3 with known variance. S283 fades a failed structural sweep
only when the closed-price path has significantly more turning points than
randomness predicts, indicating an anti-persistent, reversal-prone regime.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy275 import DEFAULT_CFG as S275_DEFAULT_CFG
from strategy282 import _turning_zscore


DEFAULT_CFG = {
    **S275_DEFAULT_CFG,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "TURNING_LOOKBACK": 64,
    "TURNING_Z_MIN": 1.50,
    "SWEEP_LOOKBACK": 10,
    "REJECTION_WICK_MIN": 0.20,
    "RECLAIM_FRACTION_MIN": 0.15,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def detect_s283(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a failed sweep in a statistically high-turning price path."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(16, int(c["TURNING_LOOKBACK"]))
        z_min = float(c["TURNING_Z_MIN"])
        sweep_lookback = max(3, int(c["SWEEP_LOOKBACK"]))
        period = max(1, int(c["ATR_PERIOD"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(lookback + 3, sweep_lookback + 2, period + 5)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
        closes = [bar["close"] for bar in bars[-lookback - 1:-1]]
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        AttributeError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    zscore, turns = _turning_zscore(closes)
    if zscore is None:
        return _wait("Turning-point statistic is unavailable")
    if zscore < z_min:
        return _wait(f"Path is not sufficiently reversal-prone (z={zscore:.2f})")

    event = bars[-1]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0:
        return _wait("Event candle has zero range")
    prior = bars[-sweep_lookback - 1:-1]
    prior_high = max(bar["high"] for bar in prior)
    prior_low = min(bar["low"] for bar in prior)
    range_width = prior_high - prior_low
    if range_width <= 0.0:
        return _wait("Prior range is degenerate")
    wick_min = float(c["REJECTION_WICK_MIN"])
    reclaim_min = float(c["RECLAIM_FRACTION_MIN"])
    lower_wick = min(event["open"], event["close"]) - event["low"]
    upper_wick = event["high"] - max(event["open"], event["close"])
    if (
        event["low"] < prior_low
        and event["close"] > prior_low + reclaim_min * range_width
        and event["close"] > event["open"]
        and lower_wick / event_range >= wick_min
    ):
        signal, side = "BUY", 1
    elif (
        event["high"] > prior_high
        and event["close"] < prior_high - reclaim_min * range_width
        and event["close"] < event["open"]
        and upper_wick / event_range >= wick_min
    ):
        signal, side = "SELL", -1
    else:
        return _wait("No failed structural sweep and reclaim")
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
        return _wait(f"Reclaim risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Reclaim risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Reclaim risk too large versus price")

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
        "pattern": f"S283 {signal} High-Turning Reclaim {rr:g}R",
        "reason": (
            f"Failed sweep in a high-turning anti-persistent path "
            f"(z={zscore:.2f}, turns={turns})"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
