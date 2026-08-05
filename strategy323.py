# -*- coding: utf-8 -*-
"""S323 - Lead-lag volume-pressure coupling release.

S323 measures nonlinear dependence between signed tick-volume pressure at
time t and the closed return at t+1.  It compares non-overlapping baseline
and recent samples, then requires the recent signed covariance and price path
to agree with a strong closed release candle.

All coupling inputs precede the release candle.  A market signal is filled at
the next bar open by the backtester.  The stop sits beyond the release extreme
plus an ATR buffer and the target is at least 7R.
"""

from __future__ import annotations

import math
from statistics import median

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy322 import _distance_correlation


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_PAIRS": 48,
    "RECENT_PAIRS": 18,
    "RECENT_DCOR_MIN": 0.42,
    "DCOR_JUMP_MIN": 0.10,
    "SIGNED_COV_MIN": 0.04,
    "PATH_EFFICIENCY_MIN": 0.20,
    "NET_MOVE_ATR_MIN": 0.45,
    "RELEASE_BODY_ATR_MIN": 0.65,
    "RELEASE_RANGE_ATR_MIN": 0.78,
    "RELEASE_CLOSE_FRACTION": 0.78,
    "SESSION_START_HOUR": 7,
    "SESSION_END_HOUR": 17,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 8.0,
    "BE_RR": 0.10,
    "CANCEL_BARS": 3,
}


def _lead_lag_sample(bars):
    """Return pressure_t and log-return_t+1 samples from closed bars."""
    if len(bars) < 8:
        return None
    positive_volumes = [
        float(bar["tick_volume"])
        for bar in bars
        if float(bar["tick_volume"]) > 0.0
    ]
    if not positive_volumes:
        return None
    volume_center = median(positive_volumes)
    if volume_center <= 0.0:
        return None

    pressures = []
    future_returns = []
    for index in range(len(bars) - 1):
        bar = bars[index]
        next_bar = bars[index + 1]
        candle_range = float(bar["high"]) - float(bar["low"])
        current_close = float(bar["close"])
        next_close = float(next_bar["close"])
        if (
            candle_range <= 0.0
            or current_close <= 0.0
            or next_close <= 0.0
        ):
            continue
        body_location = (
            float(bar["close"]) - float(bar["open"])
        ) / candle_range
        relative_volume = math.log1p(
            max(0.0, float(bar["tick_volume"])) / volume_center
        )
        pressures.append(body_location * relative_volume)
        future_returns.append(math.log(next_close / current_close))
    if len(pressures) < 6:
        return None
    return pressures, future_returns


def _coupling_state(bars):
    sample = _lead_lag_sample(bars)
    if sample is None:
        return None
    pressures, future_returns = sample
    dcor = _distance_correlation(pressures, future_returns)
    if dcor is None:
        return None
    pressure_mean = sum(pressures) / len(pressures)
    return_mean = sum(future_returns) / len(future_returns)
    covariance = sum(
        (pressure - pressure_mean) * (future_return - return_mean)
        for pressure, future_return in zip(pressures, future_returns)
    ) / len(pressures)
    pressure_variance = sum(
        (pressure - pressure_mean) ** 2 for pressure in pressures
    ) / len(pressures)
    return_variance = sum(
        (future_return - return_mean) ** 2
        for future_return in future_returns
    ) / len(future_returns)
    denominator = math.sqrt(pressure_variance * return_variance)
    if denominator <= 0.0:
        return None
    return dcor, covariance / denominator


def detect_s323(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release when volume pressure begins leading future returns."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(8, int(c["BASELINE_PAIRS"]))
        recent_count = max(6, int(c["RECENT_PAIRS"]))
        recent_min = float(c["RECENT_DCOR_MIN"])
        jump_min = float(c["DCOR_JUMP_MIN"])
        signed_cov_min = float(c["SIGNED_COV_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    gates = (recent_min, jump_min, signed_cov_min)
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: coupling gates must be finite")

    required = max(period + 5, baseline_count + recent_count + 4)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 3:-1]
        baseline = history[:baseline_count + 2]
        recent = history[baseline_count:]
        baseline_state = _coupling_state(baseline)
        recent_state = _coupling_state(recent)
        atr = _atr(bars[:-1], period)
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
    if baseline_state is None or recent_state is None:
        return _wait("Lead-lag coupling is unavailable")
    baseline_dcor, _ = baseline_state
    recent_dcor, signed_correlation = recent_state
    coupling_jump = recent_dcor - baseline_dcor
    if recent_dcor < recent_min or coupling_jump < jump_min:
        return _wait(
            f"No lead-lag coupling shift ({recent_dcor:.3f}, "
            f"jump={coupling_jump:.3f})"
        )
    if abs(signed_correlation) < signed_cov_min:
        return _wait(
            f"Lead-lag direction is weak ({signed_correlation:.3f})"
        )
    side = 1 if signed_correlation > 0.0 else -1

    net_move = recent[-1]["close"] - recent[0]["close"]
    travelled = sum(
        abs(recent[index]["close"] - recent[index - 1]["close"])
        for index in range(1, len(recent))
    )
    if travelled <= 0.0:
        return _wait("Recent path has no movement")
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Recent path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Recent net move is too small")
    if net_move * side <= 0.0:
        return _wait("Price path opposes lead-lag direction")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes lead-lag direction")
    if abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if candle_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    close_fraction = (
        (event["close"] - event["low"]) / candle_range
        if side > 0
        else (event["high"] - event["close"]) / candle_range
    )
    if close_fraction < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Release lacks directional close control")

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
        "pattern": f"S323 {signal} Lead-Lag Coupling {rr:g}R",
        "reason": (
            f"lead-lag dCor {baseline_dcor:.4f}->{recent_dcor:.4f}, "
            f"jump={coupling_jump:.4f}, signed={signed_correlation:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
