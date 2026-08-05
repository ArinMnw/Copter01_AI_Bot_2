# -*- coding: utf-8 -*-
"""S390 — Conditional Signed-Flow Partial-Correlation Release 7R.

Raw lag correlation can merely echo return autocorrelation.  S390 residualizes
both lagged signed tick-volume pressure and the next return against the prior
return, then measures their partial correlation.  A recent positive increase
over the older baseline indicates incremental order-flow information beyond
price momentum.  The causal release/risk engine is inherited from S389 with
relaxed raw-correlation gates, closed bars, next-open fill, and dynamic ATR SL.
"""

from __future__ import annotations

import math

from strategy383 import _bars, _wait
from strategy389 import DEFAULT_CFG as RELEASE_DEFAULT_CFG
from strategy389 import _pearson, detect_s389


DEFAULT_CFG = dict(RELEASE_DEFAULT_CFG)
DEFAULT_CFG.update({
    "LEAD_CORR_MIN": 0.05,
    "LEAD_CORR_RISE_MIN": 0.00,
    "PARTIAL_CORR_MIN": 0.20,
    "PARTIAL_CORR_RISE_MIN": 0.15,
    "SL_BUFFER_ATR": 0.19,
    "TP_RR": 7.0,
})

_PARTIAL_KEYS = {"PARTIAL_CORR_MIN", "PARTIAL_CORR_RISE_MIN"}


def _residuals(values, control):
    if len(values) != len(control) or len(values) < 3:
        return None
    mean_values = sum(values) / len(values)
    mean_control = sum(control) / len(control)
    centered_control = [value - mean_control for value in control]
    variance = sum(value * value for value in centered_control)
    if variance <= 0.0:
        return None
    covariance = sum(
        (value - mean_values) * centered
        for value, centered in zip(values, centered_control)
    )
    beta = covariance / variance
    return [
        value - mean_values - beta * centered
        for value, centered in zip(values, centered_control)
    ]


def _partial_flow_corr(bars):
    pressure = []
    returns = []
    for index, bar in enumerate(bars):
        body = bar["close"] - bar["open"]
        sign = 1.0 if body > 0.0 else -1.0 if body < 0.0 else 0.0
        pressure.append(sign * bar["tick_volume"])
        if index:
            returns.append(bar["close"] - bars[index - 1]["close"])
    predictors = pressure[1:-1]
    targets = returns[1:]
    controls = returns[:-1]
    residual_predictors = _residuals(predictors, controls)
    residual_targets = _residuals(targets, controls)
    if residual_predictors is None or residual_targets is None:
        return None
    return _pearson(residual_predictors, residual_targets)


def detect_s390(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return S390 when signed flow adds information beyond prior return."""
    del kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(10, int(c["RECENT_BARS"]))
        partial_min = float(c["PARTIAL_CORR_MIN"])
        partial_rise_min = float(c["PARTIAL_CORR_RISE_MIN"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (partial_min, partial_rise_min)
    ):
        return _wait("Invalid config: partial-correlation gates are invalid")
    required = baseline_count + recent_count + 1
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates[-required:])
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        baseline_partial = _partial_flow_corr(baseline)
        recent_partial = _partial_flow_corr(recent)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if baseline_partial is None or recent_partial is None:
        return _wait("Partial flow correlation is unavailable")
    partial_rise = recent_partial - baseline_partial
    if recent_partial < partial_min:
        return _wait(f"Recent partial flow correlation is weak ({recent_partial:.3f})")
    if partial_rise < partial_rise_min:
        return _wait(f"Partial flow correlation has not risen enough ({partial_rise:.3f})")

    release_cfg = {
        key: value for key, value in c.items() if key not in _PARTIAL_KEYS
    }
    payload = detect_s389(rates, tf=tf, dt_bkk=dt_bkk, cfg=release_cfg)
    if payload.get("signal") not in ("BUY", "SELL"):
        return payload
    signal = payload["signal"]
    rr = max(7.0, float(c["TP_RR"]))
    payload["pattern"] = (
        f"S390 {signal} Conditional Signed-Flow Partial Corr {rr:g}R"
    )
    payload["reason"] = (
        f"partial={recent_partial:.4f}, baseline={baseline_partial:.4f}, "
        f"rise={partial_rise:.4f}; {payload['reason']}"
    )
    return payload

