# -*- coding: utf-8 -*-
"""S388 — Joint-Tail Duration-Dependence Release 10R.

S387 measures first-order tail persistence.  S388 asks a higher-order question:
are recent joint volume/range tail events concentrated in long runs rather than
isolated pairs?  The size-biased mean run length and the longest-run share must
rise above their older baseline.  This duration dependence is intended to find
self-reinforcing liquidity cascades with enough continuity to reach a distant
10R target.  Risk and execution remain conservative through the S387 release
engine: closed-bar signals, next-open market fill, and event-extreme plus ATR SL.
"""

from __future__ import annotations

import math

from strategy383 import _bars, _quantile, _wait
from strategy385 import _joint_states, _observations
from strategy387 import DEFAULT_CFG as RELEASE_DEFAULT_CFG
from strategy387 import detect_s387


DEFAULT_CFG = dict(RELEASE_DEFAULT_CFG)
DEFAULT_CFG.update({
    "BASELINE_BARS": 80,
    "RECENT_BARS": 24,
    "MIN_TAIL_EVENTS": 4,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TAIL_DIRECTIONAL_VOLUME_MIN": 0.15,
    "MIN_LONGEST_RUN": 3,
    "RUN_MEAN_RISE_MIN": 1.00,
    "LONG_RUN_EVENT_SHARE_MIN": 0.50,
    "TP_RR": 10.0,
})

_RUN_KEYS = {
    "MIN_LONGEST_RUN",
    "RUN_MEAN_RISE_MIN",
    "LONG_RUN_EVENT_SHARE_MIN",
}


def _run_lengths(states):
    lengths = []
    current = 0
    for state in states:
        if state:
            current += 1
        elif current:
            lengths.append(current)
            current = 0
    if current:
        lengths.append(current)
    return lengths


def _run_profile(states):
    """Return event-weighted run duration, longest run and long-run share."""
    lengths = _run_lengths(states)
    events = sum(lengths)
    if not lengths or events <= 0:
        return 0.0, 0, 0.0
    size_biased_mean = sum(length * length for length in lengths) / events
    longest = max(lengths)
    long_events = sum(length for length in lengths if length >= 2)
    return size_biased_mean, longest, long_events / events


def detect_s388(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return S388 only when a release has higher-order run concentration."""
    del kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(10, int(c["RECENT_BARS"]))
        probability = float(c["TAIL_QUANTILE"])
        minimum_events = max(2, int(c["MIN_TAIL_EVENTS"]))
        minimum_longest = max(2, int(c["MIN_LONGEST_RUN"]))
        mean_rise_min = float(c["RUN_MEAN_RISE_MIN"])
        long_share_min = float(c["LONG_RUN_EVENT_SHARE_MIN"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not 0.50 <= probability <= 0.85:
        return _wait("Invalid config: tail quantile outside [0.50, 0.85]")
    if not math.isfinite(mean_rise_min) or mean_rise_min < 0.0:
        return _wait("Invalid config: run-mean rise must be non-negative")
    if not math.isfinite(long_share_min) or not 0.0 <= long_share_min <= 1.0:
        return _wait("Invalid config: long-run share outside [0, 1]")

    required = baseline_count + recent_count + 1
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates[-required:])
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        baseline_observations, _ = _observations(baseline)
        recent_observations, _ = _observations(recent)
        volume_threshold = _quantile(
            [item[0] for item in baseline_observations], probability
        )
        range_threshold = _quantile(
            [item[1] for item in baseline_observations], probability
        )
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if volume_threshold is None or range_threshold is None:
        return _wait("Baseline tail thresholds are unavailable")
    baseline_states = _joint_states(
        baseline_observations, volume_threshold, range_threshold
    )
    recent_states = _joint_states(
        recent_observations, volume_threshold, range_threshold
    )
    event_count = sum(recent_states)
    if event_count < minimum_events:
        return _wait(f"Too few recent joint-tail events ({event_count})")
    baseline_mean, _, _ = _run_profile(baseline_states)
    recent_mean, recent_longest, recent_long_share = _run_profile(recent_states)
    run_mean_rise = recent_mean - baseline_mean
    if recent_longest < minimum_longest:
        return _wait(f"Longest recent tail run is too short ({recent_longest})")
    if run_mean_rise < mean_rise_min:
        return _wait(f"Tail-run duration has not risen enough ({run_mean_rise:.3f})")
    if recent_long_share < long_share_min:
        return _wait(f"Too few events belong to long runs ({recent_long_share:.3f})")

    release_cfg = {key: value for key, value in c.items() if key not in _RUN_KEYS}
    payload = detect_s387(rates, tf=tf, dt_bkk=dt_bkk, cfg=release_cfg)
    if payload.get("signal") not in ("BUY", "SELL"):
        return payload
    signal = payload["signal"]
    rr = max(7.0, float(c["TP_RR"]))
    payload["pattern"] = f"S388 {signal} Joint-Tail Duration Dependence {rr:g}R"
    payload["reason"] = (
        f"tail events={event_count}, longest run={recent_longest}, "
        f"recent run mean={recent_mean:.4f}, baseline={baseline_mean:.4f}, "
        f"rise={run_mean_rise:.4f}, long share={recent_long_share:.4f}"
    )
    return payload
