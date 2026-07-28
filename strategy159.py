# -*- coding: utf-8 -*-
"""S159 - Multi-bar post-jump acceptance breakout with a structural 7R target."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_WINDOW": 80,
    "JUMP_SIGMA_MIN": 3.00,
    "NO_PRIOR_JUMP_BARS": 8,
    "JUMP_VOLUME_QUANTILE": 0.80,
    "JUMP_CLOSE_LOCATION_MIN": 0.80,
    "HOLD_RETRACE_MAX": 0.50,
    "BREAKOUT_CLOSE_LOCATION_MIN": 0.75,
    "MIN_HOLD_BARS": 1,
    "MAX_HOLD_BARS": 4,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.00,
    "MAX_RISK_PRICE_PCT": 0.28,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _jump_context(bars, jump_index, baseline, prior_bars, threshold):
    returns = [bars[index]["close"] - bars[index - 1]["close"]
               for index in range(1, len(bars))]
    return_index = jump_index - 1
    reference = returns[return_index - baseline:return_index]
    if len(reference) < baseline:
        return None
    median_return = _quantile(reference, 0.50)
    mad = _quantile([abs(value - median_return) for value in reference], 0.50)
    robust_sigma = max(1e-12, mad * 1.4826)
    jump_return = returns[return_index]
    jump_z = abs(jump_return - median_return) / robust_sigma
    prior = returns[max(0, return_index - prior_bars):return_index]
    isolated = not any(
        abs(value - median_return) / robust_sigma >= threshold for value in prior
    )
    return jump_z, isolated


def detect_s159(rates, tf, dt_bkk, cfg):
    """Enter the first breakout after several bars accept an isolated jump."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        baseline = max(40, int(c["BASELINE_WINDOW"]))
        prior_bars = max(1, int(c["NO_PRIOR_JUMP_BARS"]))
        period = max(1, int(c["ATR_PERIOD"]))
        min_hold = max(1, int(c["MIN_HOLD_BARS"]))
        max_hold = max(min_hold, int(c["MAX_HOLD_BARS"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = baseline + prior_bars + period + max_hold + 5
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    breakout = bars[-1]
    breakout_range = breakout["high"] - breakout["low"]
    if breakout_range <= 0.0:
        return _wait("Breakout range is zero")
    threshold = float(c["JUMP_SIGMA_MIN"])
    hold_retrace = float(c["HOLD_RETRACE_MAX"])
    candidate = None
    for hold_bars in range(min_hold, max_hold + 1):
        jump_index = len(bars) - hold_bars - 2
        jump = bars[jump_index]
        jump_range = jump["high"] - jump["low"]
        jump_body = jump["close"] - jump["open"]
        if jump_range <= 0.0 or jump_body == 0.0:
            continue
        context = _jump_context(bars, jump_index, baseline, prior_bars, threshold)
        if context is None:
            continue
        jump_z, isolated = context
        if jump_z < threshold or not isolated:
            continue
        history = bars[jump_index - baseline:jump_index]
        volume_min = _quantile(
            [bar["tick_volume"] for bar in history], c["JUMP_VOLUME_QUANTILE"]
        )
        if jump["tick_volume"] < volume_min:
            continue
        jump_location = (jump["close"] - jump["low"]) / jump_range
        holding = bars[jump_index + 1:-1]
        breakout_location = (breakout["close"] - breakout["low"]) / breakout_range
        location_min = float(c["JUMP_CLOSE_LOCATION_MIN"])
        breakout_min = float(c["BREAKOUT_CLOSE_LOCATION_MIN"])
        if jump_body > 0.0 and jump_location >= location_min:
            boundary = jump["close"] - hold_retrace * jump_body
            if (all(bar["low"] >= boundary and bar["close"] <= jump["high"] for bar in holding)
                    and breakout["close"] > jump["high"]
                    and breakout_location >= breakout_min):
                candidate = ("BUY", jump_z, boundary, hold_bars)
                break
        elif jump_body < 0.0 and jump_location <= 1.0 - location_min:
            boundary = jump["close"] - hold_retrace * jump_body
            if (all(bar["high"] <= boundary and bar["close"] >= jump["low"] for bar in holding)
                    and breakout["close"] < jump["low"]
                    and breakout_location <= 1.0 - breakout_min):
                candidate = ("SELL", jump_z, boundary, hold_bars)
                break
    if candidate is None:
        return _wait("No first breakout from a retained post-jump range")

    direction, jump_z, boundary, hold_bars = candidate
    fraction = float(c["ENTRY_RANGE_FRACTION"])
    entry = breakout["low"] + fraction * breakout_range
    if direction == "BUY":
        if entry >= breakout["close"]:
            return _wait("BUY limit is not below breakout close")
        sl = min(breakout["low"], boundary) - atr * float(c["SL_BUFFER_ATR"])
    else:
        if entry <= breakout["close"]:
            return _wait("SELL limit is not above breakout close")
        sl = max(breakout["high"], boundary) + atr * float(c["SL_BUFFER_ATR"])

    entry = round(entry, 2)
    sl = (math.floor((sl + 1e-12) * 100) / 100 if direction == "BUY"
          else math.ceil((sl - 1e-12) * 100) / 100)
    risk = entry - sl if direction == "BUY" else sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Accepted-breakout risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Accepted-breakout risk too large versus price ({risk_pct:.2f}%)")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + rr * risk if direction == "BUY" else entry - rr * risk
    tp = (math.ceil((raw_tp - 1e-12) * 100) / 100 if direction == "BUY"
          else math.floor((raw_tp + 1e-12) * 100) / 100)
    return {
        "signal": direction,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S159 {direction} Multi-Bar Jump Acceptance {rr:g}R",
        "reason": (f"Isolated jump z={jump_z:.2f}; {hold_bars} holding bars then "
                   "first directional breakout"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
