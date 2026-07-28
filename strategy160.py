# -*- coding: utf-8 -*-
"""S160 - Failed post-jump range breakout sweep with a short 7R stop."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile
from strategy159 import _jump_context


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_WINDOW": 80,
    "JUMP_SIGMA_MIN": 3.00,
    "NO_PRIOR_JUMP_BARS": 8,
    "JUMP_VOLUME_QUANTILE": 0.80,
    "JUMP_CLOSE_LOCATION_MIN": 0.80,
    "HOLD_RETRACE_MAX": 0.50,
    "MIN_HOLD_BARS": 1,
    "MAX_HOLD_BARS": 4,
    "MIN_SWEEP_ATR": 0.03,
    "REVERSAL_CLOSE_LOCATION_MAX": 0.35,
    "REVERSAL_VOLUME_QUANTILE": 0.50,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_SWEEP_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 0.70,
    "MAX_RISK_PRICE_PCT": 0.20,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s160(rates, tf, dt_bkk, cfg):
    """Fade a sweep that fails to close outside an accepted jump range."""
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

    reversal = bars[-1]
    reversal_range = reversal["high"] - reversal["low"]
    if reversal_range <= 0.0:
        return _wait("Reversal range is zero")
    reversal_location = (reversal["close"] - reversal["low"]) / reversal_range
    threshold = float(c["JUMP_SIGMA_MIN"])
    hold_retrace = float(c["HOLD_RETRACE_MAX"])
    sweep_min = atr * float(c["MIN_SWEEP_ATR"])
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
        jump_volume_min = _quantile(
            [bar["tick_volume"] for bar in history], c["JUMP_VOLUME_QUANTILE"]
        )
        reversal_volume_min = _quantile(
            [bar["tick_volume"] for bar in history], c["REVERSAL_VOLUME_QUANTILE"]
        )
        if jump["tick_volume"] < jump_volume_min or reversal["tick_volume"] < reversal_volume_min:
            continue
        jump_location = (jump["close"] - jump["low"]) / jump_range
        holding = bars[jump_index + 1:-1]
        location_min = float(c["JUMP_CLOSE_LOCATION_MIN"])
        reversal_max = float(c["REVERSAL_CLOSE_LOCATION_MAX"])
        if jump_body > 0.0 and jump_location >= location_min:
            boundary = jump["close"] - hold_retrace * jump_body
            retained = all(
                bar["low"] >= boundary and bar["close"] <= jump["high"] for bar in holding
            )
            failed = (reversal["high"] >= jump["high"] + sweep_min
                      and reversal["close"] < jump["high"]
                      and reversal_location <= reversal_max)
            if retained and failed:
                candidate = ("SELL", jump_z, hold_bars)
                break
        elif jump_body < 0.0 and jump_location <= 1.0 - location_min:
            boundary = jump["close"] - hold_retrace * jump_body
            retained = all(
                bar["high"] <= boundary and bar["close"] >= jump["low"] for bar in holding
            )
            failed = (reversal["low"] <= jump["low"] - sweep_min
                      and reversal["close"] > jump["low"]
                      and reversal_location >= 1.0 - reversal_max)
            if retained and failed:
                candidate = ("BUY", jump_z, hold_bars)
                break
    if candidate is None:
        return _wait("No failed sweep of an accepted jump range")

    direction, jump_z, hold_bars = candidate
    fraction = float(c["ENTRY_RANGE_FRACTION"])
    entry = reversal["low"] + fraction * reversal_range
    if direction == "SELL":
        if entry <= reversal["close"]:
            return _wait("SELL limit is not above reversal close")
        sl = reversal["high"] + atr * float(c["SL_SWEEP_BUFFER_ATR"])
    else:
        if entry >= reversal["close"]:
            return _wait("BUY limit is not below reversal close")
        sl = reversal["low"] - atr * float(c["SL_SWEEP_BUFFER_ATR"])

    entry = round(entry, 2)
    sl = (math.ceil((sl - 1e-12) * 100) / 100 if direction == "SELL"
          else math.floor((sl + 1e-12) * 100) / 100)
    risk = sl - entry if direction == "SELL" else entry - sl
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Failed-sweep risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Failed-sweep risk too large versus price ({risk_pct:.2f}%)")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry - rr * risk if direction == "SELL" else entry + rr * risk
    tp = (math.floor((raw_tp + 1e-12) * 100) / 100 if direction == "SELL"
          else math.ceil((raw_tp - 1e-12) * 100) / 100)
    return {
        "signal": direction,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S160 {direction} Accepted-Range Failed Sweep {rr:g}R",
        "reason": (f"Isolated jump z={jump_z:.2f}; {hold_bars} holding bars then "
                   "sweep closed back inside the accepted range"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
