# -*- coding: utf-8 -*-
"""S369 - Rogers-Satchell directional range-control release.

S369 decomposes the Rogers-Satchell range-variance estimator into upper and
lower excursion contributions.  When recent lower-excursion contribution
dominates, closes are persistently controlled near the upper range (bullish);
upper dominance indicates bearish control.  The absolute imbalance must
expand versus disjoint baseline blocks while net path and a closed release
agree on direction.

All range-control and path inputs precede the release candle.  Entry is
next-open market, SL is beyond the closed release extreme plus ATR, and TP is
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
    "CONTROL_MIN": 0.20,
    "CONTROL_RATIO_MIN": 1.20,
    "PATH_EFFICIENCY_MIN": 0.22,
    "NET_MOVE_ATR_MIN": 0.50,
    "RELEASE_BODY_ATR_MIN": 0.80,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.80,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 26.0,
    "BE_RR": 0.01,
    "CANCEL_BARS": 3,
}


def _rs_control_profile(bars):
    if len(bars) < 8:
        return None
    upper = lower = 0.0
    closes = []
    for bar in bars:
        open_price = float(bar["open"])
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        if not all(
            math.isfinite(value) and value > 0.0
            for value in (open_price, high, low, close)
        ):
            return None
        upper += math.log(high / open_price) * math.log(high / close)
        lower += math.log(low / open_price) * math.log(low / close)
        closes.append(close)
    total = upper + lower
    if not math.isfinite(total) or total <= 1e-18:
        return None
    control = (lower - upper) / total
    net_move = closes[-1] - closes[0]
    travelled = sum(
        abs(closes[index] - closes[index - 1])
        for index in range(1, len(closes))
    )
    if travelled <= 0.0 or abs(net_move) <= 1e-12 or abs(control) <= 1e-12:
        return None
    side = 1 if control > 0.0 else -1
    if net_move * side <= 0.0:
        return None
    path_efficiency = abs(net_move) / travelled
    return abs(control), side, net_move, path_efficiency


def detect_s369(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after Rogers-Satchell range control expands."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        control_min = float(c["CONTROL_MIN"])
        control_ratio_min = float(c["CONTROL_RATIO_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (control_min, control_ratio_min)
    ):
        return _wait("Invalid config: range-control gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        # Only the required tail participates in the detector.  Limiting the
        # conversion keeps rolling backtests fast without changing any input
        # used by the signal.
        bars = _bars(rates[-required:])
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        baseline_controls = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _rs_control_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_controls.append(profile[0])
        recent_profile = _rs_control_profile(recent)
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
    if recent_profile is None or not baseline_controls:
        return _wait("Rogers-Satchell control profile is unavailable")

    control, side, net_move, path_efficiency = recent_profile
    baseline_control = statistics.median(baseline_controls)
    if baseline_control <= 0.0:
        return _wait("Baseline range control is zero")
    control_ratio = control / baseline_control
    if control < control_min or control_ratio < control_ratio_min:
        return _wait(
            f"No range-control expansion ({baseline_control:.3f}->"
            f"{control:.3f}, ratio={control_ratio:.3f})"
        )
    if path_efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Controlled path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Controlled net move is too small")

    body = float(event["close"]) - float(event["open"])
    candle_range = float(event["high"]) - float(event["low"])
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes range-control direction")
    if abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if candle_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    close_fraction = (
        (float(event["close"]) - float(event["low"])) / candle_range
        if side > 0
        else (float(event["high"]) - float(event["close"])) / candle_range
    )
    if close_fraction < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Release lacks directional close control")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(float(event["close"]), 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor(
            (float(event["low"]) - sl_buffer + 1e-12) * 100.0
        ) / 100.0
    else:
        sl = math.ceil(
            (float(event["high"]) + sl_buffer - 1e-12) * 100.0
        ) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Release risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Release risk too large versus price")

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
        "pattern": f"S369 {signal} RS Range Control {rr:g}R",
        "reason": (
            f"RS control {baseline_control:.4f}->{control:.4f}, "
            f"ratio={control_ratio:.4f}, path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
