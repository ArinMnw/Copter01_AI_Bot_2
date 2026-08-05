# -*- coding: utf-8 -*-
"""S413 — Robust-Shape / Gap-Response Decoupled BUY Release 7R.

S413 orthogonalizes the Sn/Qn robust-shape displacement factor from the
opening-gap response factor.  It keeps S410's 28-bar BUY shape releases only
when absolute gap-to-intrabar correlation is low, aiming to retain distribution
shape repricing while avoiding exposure already represented by weighted S409.
All inputs are closed bars; the market payload fills next-open with >=7R.
"""

from __future__ import annotations

import math

from strategy383 import _bars, _wait
from strategy409 import _response_metrics
from strategy410 import detect_s410


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 84,
    "RECENT_BARS": 28,
    "SHAPE_RATIO_MIN": 1.04,
    "SHAPE_RISE_MIN": 0.03,
    "SN_SCALE_RATIO_MIN": 1.00,
    "SN_RISE_ATR_MIN": 0.00,
    "GAP_RESPONSE_ABS_MAX": 0.20,
    "PATH_EFFICIENCY_MIN": 0.12,
    "NET_MOVE_ATR_MIN": 0.35,
    "EVENT_VOLUME_RATIO_MIN": 1.00,
    "EVENT_BODY_ATR_MIN": 0.45,
    "EVENT_RANGE_ATR_MIN": 0.65,
    "EVENT_BODY_FRACTION_MIN": 0.60,
    "EVENT_CLOSE_FRACTION": 0.70,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.18,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": False,
    "TP_RR": 7.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def detect_s413(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a gap-decoupled S410 payload using closed bars only."""
    del kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        corr_max = float(c["GAP_RESPONSE_ABS_MAX"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: decoupling windows are inconsistent")
    if not math.isfinite(corr_max) or not 0.0 <= corr_max <= 1.0:
        return _wait("Invalid config: gap-response cap is invalid")
    required = max(int(c["ATR_PERIOD"]) + 3,
                   baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates[-required:])
        recent = bars[-recent_count - 1:-1]
        response = _response_metrics(recent)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if response is None:
        return _wait("Gap-response correlation is unavailable")
    absolute_corr = abs(response["correlation"])
    if absolute_corr > corr_max:
        return _wait(
            f"Gap response is not decoupled ({absolute_corr:.3f}>{corr_max:.3f})"
        )

    nested_cfg = dict(c)
    nested_cfg.update({
        "CONTRACT_SHAPE": False,
        "FADE_PATH": False,
    })
    payload = detect_s410(rates, tf, dt_bkk, nested_cfg)
    if payload.get("signal") == "WAIT":
        return payload
    if payload["signal"] == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    payload = dict(payload)
    payload["pattern"] = (
        f"S413 {payload['signal']} Sn-Qn Gap-Decoupled {float(c['TP_RR']):g}R"
    )
    payload["reason"] = (
        f"gap_response_abs={absolute_corr:.4f}, "
        f"gap_bias={response['gap_bias']:.4f}; {payload['reason']}"
    )
    return payload
