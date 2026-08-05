# -*- coding: utf-8 -*-
"""S391 — Conditional Signed-Flow Exhaustion Reversal 7R.

S390 falsified positive partial-correlation continuation.  S391 tests the
opposite institutional interpretation: after controlling for prior return,
signed-flow pressure that becomes strongly negatively related to the next
return represents exhausted aggressive flow and passive absorption.  A strong
release candle is faded only when the recent negative partial correlation has
deteriorated from its older baseline.  The stop sits beyond the release extreme
plus ATR; market execution is evaluated at the next open without look-ahead.
"""

from __future__ import annotations

import math

from strategy383 import _atr, _bars, _wait
from strategy389 import DEFAULT_CFG as RELEASE_DEFAULT_CFG
from strategy389 import detect_s389
from strategy390 import _partial_flow_corr


DEFAULT_CFG = dict(RELEASE_DEFAULT_CFG)
DEFAULT_CFG.update({
    "LEAD_CORR_MIN": -1.00,
    "LEAD_CORR_RISE_MIN": -1.00,
    "NEGATIVE_PARTIAL_MIN": 0.20,
    "PARTIAL_DROP_MIN": 0.15,
    "SL_BUFFER_ATR": 0.19,
    "TP_RR": 7.0,
})

_EXHAUSTION_KEYS = {"NEGATIVE_PARTIAL_MIN", "PARTIAL_DROP_MIN"}


def detect_s391(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a reversal when conditional signed flow indicates exhaustion."""
    del kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(30, int(c["BASELINE_BARS"]))
        recent_count = max(10, int(c["RECENT_BARS"]))
        negative_min = float(c["NEGATIVE_PARTIAL_MIN"])
        drop_min = float(c["PARTIAL_DROP_MIN"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (negative_min, drop_min)
    ):
        return _wait("Invalid config: exhaustion gates are invalid")
    required = max(period + 3, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates[-required:])
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        baseline_partial = _partial_flow_corr(baseline)
        recent_partial = _partial_flow_corr(recent)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if baseline_partial is None or recent_partial is None or atr <= 0.0:
        return _wait("Conditional flow or ATR is unavailable")
    negative_strength = -recent_partial
    partial_drop = baseline_partial - recent_partial
    if negative_strength < negative_min:
        return _wait(f"Conditional flow is not negative enough ({recent_partial:.3f})")
    if partial_drop < drop_min:
        return _wait(f"Conditional flow has not deteriorated enough ({partial_drop:.3f})")

    release_cfg = {
        key: value for key, value in c.items() if key not in _EXHAUSTION_KEYS
    }
    continuation = detect_s389(rates, tf=tf, dt_bkk=dt_bkk, cfg=release_cfg)
    if continuation.get("signal") not in ("BUY", "SELL"):
        return continuation
    continuation_signal = continuation["signal"]
    signal = "SELL" if continuation_signal == "BUY" else "BUY"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    side = 1 if signal == "BUY" else -1
    entry = round(event["close"], 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor((event["low"] - sl_buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + sl_buffer - 1e-12) * 100.0) / 100.0
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
        "pattern": f"S391 {signal} Conditional Flow Exhaustion {rr:g}R",
        "reason": (
            f"partial={recent_partial:.4f}, baseline={baseline_partial:.4f}, "
            f"drop={partial_drop:.4f}; fade {continuation_signal} release"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
