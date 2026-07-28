# -*- coding: utf-8 -*-
"""S250 - CUSUM return-change-point structural breakout, 10R.

A fixed historical return baseline standardizes a recent monitoring window.
One-sided cumulative sums must cross a control threshold on the current closed
bar, identifying a fresh directional process shift rather than an already
mature trend.  The shift must align with an efficient range break.
"""

from __future__ import annotations

import math
from statistics import pstdev

from strategy119 import _bars
from strategy197 import _wait
from strategy232 import DEFAULT_CFG as S232_DEFAULT_CFG
from strategy232 import detect_s232


DEFAULT_CFG = {
    **S232_DEFAULT_CFG,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "CUSUM_BASELINE_WINDOW": 64,
    "CUSUM_MONITOR_WINDOW": 16,
    "CUSUM_THRESHOLD": 3.00,
    "CUSUM_DRIFT": 0.10,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
}


def _cusum_path(values, mean, scale, drift):
    positive = negative = 0.0
    states = []
    for value in values:
        score = (value - mean) / scale
        positive = max(0.0, positive + score - drift)
        negative = min(0.0, negative + score + drift)
        states.append((positive, negative))
    return states


def detect_s250(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade an efficient range break on a fresh one-sided CUSUM crossing."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        baseline_window = max(20, int(c["CUSUM_BASELINE_WINDOW"]))
        monitor_window = max(4, int(c["CUSUM_MONITOR_WINDOW"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = baseline_window + monitor_window + 4
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        closes = [
            float(bar["close"])
            for bar in bars[-baseline_window - monitor_window - 2:]
        ]
        if min(closes) <= 0.0:
            return _wait("Non-positive close")
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
        ]
        baseline = returns[:baseline_window]
        monitored = returns[-monitor_window:]
        mean = sum(baseline) / len(baseline)
        scale = pstdev(baseline)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if scale <= 0.0:
        return _wait("Baseline return variance is zero")
    path = _cusum_path(monitored, mean, scale, float(c["CUSUM_DRIFT"]))
    if len(path) < 2:
        return _wait("CUSUM path is unavailable")
    threshold = float(c["CUSUM_THRESHOLD"])
    previous, current = path[-2], path[-1]
    if previous[0] < threshold <= current[0]:
        expected_side = "BUY"
        statistic = current[0]
    elif previous[1] > -threshold >= current[1]:
        expected_side = "SELL"
        statistic = -current[1]
    else:
        return _wait(
            f"No fresh CUSUM threshold crossing "
            f"(+{current[0]:.2f}/{current[1]:.2f})"
        )
    if expected_side == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY CUSUM branch is disabled")
    if expected_side == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL CUSUM branch is disabled")

    breakout_cfg = dict(c)
    breakout_cfg["RS_COMPRESSION_MAX"] = math.inf
    signal = detect_s232(rates, tf, dt_bkk, breakout_cfg, **kwargs)
    if signal.get("signal") != expected_side:
        return _wait("CUSUM shift does not align with a structural range break")
    rr = max(7.0, float(c["TP_RR"]))
    signal = dict(signal)
    signal["pattern"] = f"S250 {expected_side} CUSUM Change-Point Break {rr:g}R"
    signal["reason"] = (
        f"Fresh {expected_side} return-process shift with structural break "
        f"(CUSUM={statistic:.2f})"
    )
    return signal
