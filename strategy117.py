# -*- coding: utf-8 -*-
"""S117 — Variance-Ratio Regime Router (S115 + S116).

S115's continuation setup was too sparse, while S116's VWAP fade traded
against persistent moves.  S117 combines their lessons rather than blindly
combining their orders: a Lo–MacKinlay-style variance ratio routes persistent
returns to a relaxed S115 continuation detector and anti-persistent returns to
S116's session VWAP fade.  The neutral regime does not trade.
"""

from __future__ import annotations

import math

import strategy115
import strategy116


DEFAULT_CFG = {
    "VR_LOOKBACK": 48,
    "VR_LAG": 4,
    "TREND_VR_MIN": 1.10,
    "MEAN_REVERT_VR_MAX": 0.90,
    # S115 is relaxed enough to create samples but still preserves BOS/FVG/FTR.
    "S115_CFG": {
        "BOS_BODY_ATR": 0.70,
        "BOS_CLOSE_BEYOND_ATR": 0.05,
        "BOS_VOLUME_MULT": 1.00,
        "BOS_MIN_CLV": 0.40,
        "FVG_MIN_ATR": 0.08,
        "FVG_MAX_ATR": 2.00,
        "FTR_TOUCH_TOL_ATR": 0.25,
        "FTR_MAX_GAP_PENETRATION": 0.50,
        "FTR_MAX_VOLUME_VS_BOS": 0.95,
        "FTR_MAX_RANGE_ATR": 2.20,
        "CONFIRM_BODY_ATR": 0.12,
        "CONFIRM_BREAK_ATR": 0.00,
        "CONFIRM_MIN_CLV": 0.30,
        "CONFIRM_VOLUME_MULT": 0.75,
    },
    "S116_CFG": {},
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _variance(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _variance_ratio(rates, lookback, lag):
    closes = [float(bar["close"]) for bar in rates[-lookback - lag:]]
    if any(not math.isfinite(value) or value <= 0.0 for value in closes):
        return None
    returns = [math.log(closes[index] / closes[index - 1])
               for index in range(1, len(closes))]
    if len(returns) < lookback:
        return None
    returns = returns[-lookback:]
    one_variance = _variance(returns)
    if one_variance <= 0.0:
        return None
    aggregated = [sum(returns[index - lag + 1:index + 1])
                  for index in range(lag - 1, len(returns))]
    return _variance(aggregated) / (lag * one_variance)


def _route_payload(payload, variance_ratio, source):
    if payload.get("signal") not in ("BUY", "SELL"):
        return _wait(
            f"VR={variance_ratio:.2f} routed to {source}, but source returned: "
            f"{payload.get('reason', 'WAIT')}"
        )
    result = dict(payload)
    setup = str(payload.get("pattern", source)).split(" ", 1)[-1]
    result["pattern"] = f"S117 {source} {setup}"
    result["reason"] = (
        f"Variance ratio={variance_ratio:.2f} selected {source}; "
        f"{payload['reason']}"
    )
    return result


def detect_s117(rates, tf, dt_bkk, cfg):
    """Route closed bars to continuation or mean-reversion by return regime."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback_raw, lag_raw = float(c["VR_LOOKBACK"]), float(c["VR_LAG"])
        if not lookback_raw.is_integer() or not lag_raw.is_integer():
            return _wait("VR_LOOKBACK and VR_LAG must be integers")
        lookback, lag = int(lookback_raw), int(lag_raw)
        trend_min = float(c["TREND_VR_MIN"])
        mean_max = float(c["MEAN_REVERT_VR_MAX"])
        if lookback < 12 or lag < 2 or lag >= lookback:
            return _wait("Invalid variance-ratio windows")
        if not 0.0 < mean_max < trend_min:
            return _wait("Regime thresholds must satisfy 0 < mean < trend")
    except (KeyError, TypeError, ValueError, OverflowError):
        return _wait("Invalid S117 cfg")
    if rates is None or len(rates) < max(100, lookback + lag + 1):
        return _wait("Not enough data")
    if dt_bkk is None:
        return _wait("dt_bkk is required")
    try:
        ratio = _variance_ratio(rates, lookback, lag)
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return _wait("Invalid rates")
    if ratio is None or not math.isfinite(ratio):
        return _wait("Variance ratio is unavailable")

    if ratio >= trend_min:
        source_cfg = dict(DEFAULT_CFG["S115_CFG"])
        source_cfg.update(c.get("S115_CFG") or {})
        payload = strategy115.detect_s115(rates, tf, dt_bkk, source_cfg)
        return _route_payload(payload, ratio, "S115")
    if ratio <= mean_max:
        source_cfg = dict(DEFAULT_CFG["S116_CFG"])
        source_cfg.update(c.get("S116_CFG") or {})
        payload = strategy116.detect_s116(rates, tf, dt_bkk, source_cfg)
        return _route_payload(payload, ratio, "S116")
    return _wait(f"Neutral variance-ratio regime ({ratio:.2f})")
