# -*- coding: utf-8 -*-
"""S158 - Post-jump acceptance continuation with an optimized 80R target."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_WINDOW": 80,
    "JUMP_SIGMA_MIN": 3.00,
    "NO_PRIOR_JUMP_BARS": 8,
    "JUMP_CLOSE_LOCATION_MIN": 0.80,
    "JUMP_VOLUME_QUANTILE": 0.80,
    "ACCEPTANCE_RETRACE_MAX": 0.50,
    "CONFIRM_CLOSE_FRACTION": 0.80,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 0.90,
    "MAX_RISK_PRICE_PCT": 0.25,
    "TP_RR": 80.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s158(rates, tf, dt_bkk, cfg):
    """Trade only after the bar following a robust jump accepts the new range."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        baseline = max(40, int(c["BASELINE_WINDOW"]))
        prior_bars = max(1, int(c["NO_PRIOR_JUMP_BARS"]))
        period = max(1, int(c["ATR_PERIOD"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < baseline + prior_bars + period + 4 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-2], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    returns = [bars[index]["close"] - bars[index - 1]["close"]
               for index in range(1, len(bars))]
    reference = returns[-baseline - prior_bars - 2:-prior_bars - 2]
    median_return = _quantile(reference, 0.50)
    mad = _quantile([abs(value - median_return) for value in reference], 0.50)
    robust_sigma = max(1e-12, mad * 1.4826)
    jump_return = returns[-2]
    jump_z = abs(jump_return - median_return) / robust_sigma
    threshold = float(c["JUMP_SIGMA_MIN"])
    if jump_z < threshold:
        return _wait("Previous bar was not a robust jump")
    if any(abs(value - median_return) / robust_sigma >= threshold
           for value in returns[-prior_bars - 2:-2]):
        return _wait("Previous jump was not isolated")

    jump = bars[-2]
    confirm = bars[-1]
    jump_range = jump["high"] - jump["low"]
    confirm_range = confirm["high"] - confirm["low"]
    jump_body = jump["close"] - jump["open"]
    if jump_range <= 0.0 or confirm_range <= 0.0 or jump_body == 0.0:
        return _wait("Jump or confirmation range is zero")
    jump_location = (jump["close"] - jump["low"]) / jump_range
    history = bars[-baseline - 2:-2]
    volume_min = _quantile([bar["tick_volume"] for bar in history], c["JUMP_VOLUME_QUANTILE"])
    if jump["tick_volume"] < volume_min:
        return _wait("Jump volume is below empirical threshold")

    retrace = float(c["ACCEPTANCE_RETRACE_MAX"])
    confirm_fraction = float(c["CONFIRM_CLOSE_FRACTION"])
    entry_fraction = float(c["ENTRY_RANGE_FRACTION"])
    if jump_body > 0.0 and jump_location >= float(c["JUMP_CLOSE_LOCATION_MIN"]):
        acceptance_floor = jump["close"] - retrace * jump_body
        confirm_location = (confirm["close"] - confirm["low"]) / confirm_range
        if confirm["low"] < acceptance_floor or confirm_location < confirm_fraction:
            return _wait("Bullish jump was not accepted by the confirmation bar")
        direction = "BUY"
        entry = confirm["low"] + entry_fraction * confirm_range
        if entry >= confirm["close"]:
            return _wait("BUY limit is not below confirmation close")
        sl = min(confirm["low"], acceptance_floor) - atr * float(c["SL_BUFFER_ATR"])
    elif jump_body < 0.0 and jump_location <= 1.0 - float(c["JUMP_CLOSE_LOCATION_MIN"]):
        acceptance_ceiling = jump["close"] - retrace * jump_body
        confirm_location = (confirm["close"] - confirm["low"]) / confirm_range
        if confirm["high"] > acceptance_ceiling or confirm_location > 1.0 - confirm_fraction:
            return _wait("Bearish jump was not accepted by the confirmation bar")
        direction = "SELL"
        entry = confirm["low"] + entry_fraction * confirm_range
        if entry <= confirm["close"]:
            return _wait("SELL limit is not above confirmation close")
        sl = max(confirm["high"], acceptance_ceiling) + atr * float(c["SL_BUFFER_ATR"])
    else:
        return _wait("Jump did not close near its directional extreme")

    entry = round(entry, 2)
    sl = (math.floor((sl + 1e-12) * 100) / 100 if direction == "BUY"
          else math.ceil((sl - 1e-12) * 100) / 100)
    risk = entry - sl if direction == "BUY" else sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Acceptance risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Acceptance risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S158 {direction} Post-Jump Acceptance {rr:g}R",
        "reason": (f"Robust jump z={jump_z:.2f}; next bar retained "
                   f"{(1.0 - retrace) * 100:.0f}% of the jump body"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
