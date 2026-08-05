# -*- coding: utf-8 -*-
"""S368 - Bipower-variation jump-exhaustion reversal.

S368 estimates continuous return variance with realized bipower variation.
The closed event candle must be a statistically large jump in the direction
of a preceding price run, yet reject the jump-side extreme before close.  The
trade fades that failed auction after the candle is fully closed.

All baseline and pre-shock features precede the event candle.  Entry is
next-open market, SL is beyond the rejected extreme plus ATR, and TP is at
least 7R.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 40,
    "PRE_SHOCK_BARS": 12,
    "JUMP_RATIO_MIN": 3.0,
    "EVENT_RETURN_ATR_MIN": 0.50,
    "EVENT_RANGE_ATR_MIN": 1.00,
    "PRE_SHOCK_NET_ATR_MIN": 0.20,
    "PRE_SHOCK_PATH_EFFICIENCY_MIN": 0.08,
    "REJECTION_WICK_FRACTION_MIN": 0.10,
    "RECOVERY_FRACTION_MIN": 0.40,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.06,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 3.00,
    "MAX_RISK_PRICE_PCT": 0.40,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 7.0,
    "BE_RR": 0.10,
    "CANCEL_BARS": 3,
}


def _bipower_variation(bars):
    if len(bars) < 8:
        return None
    closes = [float(bar["close"]) for bar in bars]
    if not all(math.isfinite(value) and value > 0.0 for value in closes):
        return None
    returns = [
        math.log(closes[index] / closes[index - 1])
        for index in range(1, len(closes))
    ]
    products = [
        abs(returns[index - 1]) * abs(returns[index])
        for index in range(1, len(returns))
    ]
    if not products:
        return None
    bpv = math.pi / 2.0 * sum(products) / len(products)
    return bpv if math.isfinite(bpv) and bpv > 0.0 else None


def _path_profile(bars):
    if len(bars) < 4:
        return None
    closes = [float(bar["close"]) for bar in bars]
    net_move = closes[-1] - closes[0]
    travelled = sum(
        abs(closes[index] - closes[index - 1])
        for index in range(1, len(closes))
    )
    if travelled <= 0.0 or abs(net_move) <= 1e-12:
        return None
    return (1 if net_move > 0.0 else -1), net_move, abs(net_move) / travelled


def detect_s368(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a rejected jump after a directional run."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(12, int(c["BASELINE_BARS"]))
        pre_shock_count = max(4, int(c["PRE_SHOCK_BARS"]))
        jump_ratio_min = float(c["JUMP_RATIO_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not math.isfinite(jump_ratio_min) or jump_ratio_min <= 0.0:
        return _wait("Invalid config: jump ratio is invalid")

    required = max(period + 3, baseline_count + 2, pre_shock_count + 2)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        previous = bars[-2]
        baseline = bars[-baseline_count - 1:-1]
        pre_shock = bars[-pre_shock_count - 1:-1]
        bpv = _bipower_variation(baseline)
        path = _path_profile(pre_shock)
        atr = _atr(bars[:-1], period)
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        ZeroDivisionError,
        AttributeError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0 or bpv is None or path is None:
        return _wait("Jump baseline is unavailable")

    previous_close = float(previous["close"])
    event_close = float(event["close"])
    if previous_close <= 0.0 or event_close <= 0.0:
        return _wait("Non-positive price")
    event_return = math.log(event_close / previous_close)
    if abs(event_return) <= 1e-12:
        return _wait("Event has no close-to-close jump")
    shock_side = 1 if event_return > 0.0 else -1
    jump_ratio = event_return * event_return / bpv
    if jump_ratio < jump_ratio_min:
        return _wait(f"No bipower jump ({jump_ratio:.3f})")

    path_side, pre_net, path_efficiency = path
    if path_side != shock_side:
        return _wait("Jump opposes the pre-shock run")
    if abs(pre_net) < atr * float(c["PRE_SHOCK_NET_ATR_MIN"]):
        return _wait("Pre-shock run is too small")
    if path_efficiency < float(c["PRE_SHOCK_PATH_EFFICIENCY_MIN"]):
        return _wait(f"Pre-shock path is inefficient ({path_efficiency:.3f})")

    candle_range = float(event["high"]) - float(event["low"])
    if candle_range <= 0.0:
        return _wait("Event range is zero")
    if abs(event_close - previous_close) < atr * float(c["EVENT_RETURN_ATR_MIN"]):
        return _wait("Jump displacement is too small versus ATR")
    if candle_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Jump range is too small versus ATR")

    if shock_side > 0:
        rejection_wick = float(event["high"]) - max(
            float(event["open"]), event_close
        )
        recovery = (float(event["high"]) - event_close) / candle_range
    else:
        rejection_wick = min(
            float(event["open"]), event_close
        ) - float(event["low"])
        recovery = (event_close - float(event["low"])) / candle_range
    wick_fraction = rejection_wick / candle_range
    if wick_fraction < float(c["REJECTION_WICK_FRACTION_MIN"]):
        return _wait(f"Jump-side wick is too small ({wick_fraction:.3f})")
    if recovery < float(c["RECOVERY_FRACTION_MIN"]):
        return _wait(f"Jump recovery is weak ({recovery:.3f})")

    side = -shock_side
    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(event_close, 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor(
            (float(event["low"]) - sl_buffer + 1e-12) * 100.0
        ) / 100.0
    else:
        sl = math.ceil(
            (float(event["high"]) + sl_buffer - 1e-12) * 100.0
        ) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Rejected-jump risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Rejected-jump risk too large versus price")

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
        "pattern": f"S368 {signal} Bipower Jump Exhaustion {rr:g}R",
        "reason": (
            f"jump/bpv={jump_ratio:.4f}, shock={event_return:.6f}, "
            f"pre_path={path_efficiency:.4f}, wick={wick_fraction:.4f}, "
            f"recovery={recovery:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
