# -*- coding: utf-8 -*-
"""S150 — Empirical low-impact/high-volume absorption reversal, 7R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "LOOKBACK": 120,
    "VOLUME_QUANTILE": 0.85,
    "RANGE_QUANTILE_MAX": 0.55,
    "IMPACT_QUANTILE_MAX": 0.30,
    "ANCHOR_BODY_MIN_ATR": 0.05,
    "CONFIRM_BODY_MIN_ATR": 0.30,
    "BREAK_BUFFER_ATR": 0.03,
    "SL_ANCHOR_BUFFER_ATR": 0.10,
    "MAX_RISK_ATR": 1.25,
    "MAX_RISK_PRICE_PCT": 0.40,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _impact(bar):
    volume = max(1.0, bar["tick_volume"])
    return abs(bar["close"] - bar["open"]) / volume


def detect_s150(rates, tf, dt_bkk, cfg):
    """Detect absorbed effort followed by a closed opposite breakout."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        lookback = max(40, int(c["LOOKBACK"]))
        period = max(1, int(c["ATR_PERIOD"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < lookback + period + 3 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    history = bars[-lookback - 2:-2]
    anchor, latest = bars[-2], bars[-1]
    ranges = [bar["high"] - bar["low"] for bar in history]
    volume_min = _quantile([bar["tick_volume"] for bar in history], c["VOLUME_QUANTILE"])
    range_max = _quantile(ranges, c["RANGE_QUANTILE_MAX"])
    impact_max = _quantile([_impact(bar) for bar in history], c["IMPACT_QUANTILE_MAX"])
    anchor_range = anchor["high"] - anchor["low"]
    anchor_body = anchor["close"] - anchor["open"]
    if (anchor["tick_volume"] < volume_min or anchor_range > range_max
            or _impact(anchor) > impact_max
            or abs(anchor_body) < atr * float(c["ANCHOR_BODY_MIN_ATR"])):
        return _wait("No empirical high-effort/low-impact absorption anchor")

    confirm_body = latest["close"] - latest["open"]
    break_buffer = atr * float(c["BREAK_BUFFER_ATR"])
    if anchor_body < 0.0 and confirm_body >= atr * float(c["CONFIRM_BODY_MIN_ATR"]):
        if latest["close"] <= anchor["high"] + break_buffer:
            return _wait("BUY absorption lacks closed breakout confirmation")
        direction, entry = "BUY", round(anchor["high"], 2)
        sl = math.floor((anchor["low"] - atr * float(c["SL_ANCHOR_BUFFER_ATR"]) + 1e-12)
                        * 100) / 100
        risk = entry - sl
    elif anchor_body > 0.0 and confirm_body <= -atr * float(c["CONFIRM_BODY_MIN_ATR"]):
        if latest["close"] >= anchor["low"] - break_buffer:
            return _wait("SELL absorption lacks closed breakout confirmation")
        direction, entry = "SELL", round(anchor["low"], 2)
        sl = math.ceil((anchor["high"] + atr * float(c["SL_ANCHOR_BUFFER_ATR"]) - 1e-12)
                       * 100) / 100
        risk = sl - entry
    else:
        return _wait("Latest bar does not reverse absorbed effort")
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Absorption structure risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Absorption risk too large versus price ({risk_pct:.2f}%)")
    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + rr * risk if direction == "BUY" else entry - rr * risk
    tp = (math.ceil((raw_tp - 1e-12) * 100) / 100 if direction == "BUY"
          else math.floor((raw_tp + 1e-12) * 100) / 100)
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "order_type": "limit",
        "pattern": f"S150 {direction} Low-Impact Absorption {rr:g}R",
        "reason": (f"Anchor volume={anchor['tick_volume']:.0f}, range={anchor_range / atr:.2f}ATR, "
                   f"impact={_impact(anchor):.6f}; opposite breakout confirmed"),
        "be_rr": float(c["BE_RR"]), "cancel_bars": int(c["CANCEL_BARS"]),
    }
