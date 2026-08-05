# -*- coding: utf-8 -*-
"""S360 - Realized-semivariance exhaustion reversal.

S360 splits closed-return energy into upside and downside realized
semivariances.  When one side's energy share becomes extreme and shifts above
disjoint baseline blocks, it waits for an opposite closed rejection candle and
fades the exhausted energy imbalance.

All semivariance and path inputs precede the reversal candle.  Entry is
next-open market, SL is beyond the closed reversal extreme plus ATR, and TP is
at least 7R.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 80,
    "RECENT_BARS": 20,
    "DOMINANT_SEMIVARIANCE_MIN": 0.68,
    "SEMIVARIANCE_SHIFT_MIN": 0.12,
    "NET_MOVE_ATR_MIN": 0.45,
    "RELEASE_BODY_ATR_MIN": 0.72,
    "RELEASE_RANGE_ATR_MIN": 0.90,
    "RELEASE_CLOSE_FRACTION": 0.72,
    "REJECTION_WICK_FRACTION_MIN": 0.18,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 8.0,
    "BE_RR": 0.08,
    "CANCEL_BARS": 3,
}


def _semivariance_profile(bars):
    if len(bars) < 8:
        return None
    closes = [float(bar["close"]) for bar in bars]
    if not all(math.isfinite(value) for value in closes):
        return None
    returns = [
        closes[index] - closes[index - 1]
        for index in range(1, len(closes))
    ]
    upside = sum(value * value for value in returns if value > 0.0)
    downside = sum(value * value for value in returns if value < 0.0)
    total = upside + downside
    if total <= 1e-18:
        return None
    if upside >= downside:
        energy_side = 1
        dominant_share = upside / total
    else:
        energy_side = -1
        dominant_share = downside / total
    net_move = closes[-1] - closes[0]
    if abs(net_move) <= 1e-12 or net_move * energy_side <= 0.0:
        return None
    return dominant_share, energy_side, net_move


def detect_s360(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a dominant realized-semivariance regime after closed rejection."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        dominant_min = float(c["DOMINANT_SEMIVARIANCE_MIN"])
        shift_min = float(c["SEMIVARIANCE_SHIFT_MIN"])
        wick_min = float(c["REJECTION_WICK_FRACTION_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (dominant_min, shift_min, wick_min)
    ):
        return _wait("Invalid config: semivariance gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        baseline_shares = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _semivariance_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_shares.append(profile[0])
        recent_profile = _semivariance_profile(recent)
        atr = _atr(bars[:-1], period)
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        ZeroDivisionError,
        AttributeError,
        statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    if recent_profile is None or not baseline_shares:
        return _wait("Semivariance profile is unavailable")

    dominant_share, energy_side, net_move = recent_profile
    baseline_share = statistics.median(baseline_shares)
    share_shift = dominant_share - baseline_share
    if dominant_share < dominant_min or share_shift < shift_min:
        return _wait(
            f"No semivariance exhaustion "
            f"({baseline_share:.3f}->{dominant_share:.3f}, "
            f"shift={share_shift:.3f})"
        )
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Semivariance path net move is too small")

    side = -energy_side
    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("No reversal against dominant semivariance")
    if abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Reversal body is too small versus ATR")
    if candle_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Reversal range is too small versus ATR")
    close_fraction = (
        (event["close"] - event["low"]) / candle_range
        if side > 0
        else (event["high"] - event["close"]) / candle_range
    )
    rejection_wick = (
        min(event["open"], event["close"]) - event["low"]
        if side > 0
        else event["high"] - max(event["open"], event["close"])
    ) / candle_range
    if close_fraction < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Reversal lacks directional close control")
    if rejection_wick < wick_min:
        return _wait(f"Rejection wick is too small ({rejection_wick:.3f})")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(event["close"], 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor(
            (event["low"] - sl_buffer + 1e-12) * 100.0
        ) / 100.0
    else:
        sl = math.ceil(
            (event["high"] + sl_buffer - 1e-12) * 100.0
        ) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Reversal risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Reversal risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    tp = (
        math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
        if side > 0
        else math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    )
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S360 {signal} Semivariance Reversal {rr:g}R",
        "reason": (
            f"dominant semivariance {baseline_share:.4f}->"
            f"{dominant_share:.4f}, shift={share_shift:.4f}, "
            f"energy_side={energy_side:+d}, wick={rejection_wick:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
