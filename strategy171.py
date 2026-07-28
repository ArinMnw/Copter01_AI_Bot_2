# -*- coding: utf-8 -*-
"""S171 - Return-persistence structural breakout retrace with a 7R target."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "PERSISTENCE_WINDOW": 48,
    "AUTOCORR_MIN": 0.12,
    "NET_MOVE_MIN_ATR": 0.60,
    "BREAKOUT_LOOKBACK": 10,
    "BREAKOUT_BODY_MIN_ATR": 0.45,
    "BREAKOUT_CLOSE_EDGE": 0.68,
    "BREAKOUT_VOLUME_QUANTILE": 0.60,
    "ENTRY_BODY_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.06,
    "MAX_RISK_ATR": 1.10,
    "MAX_RISK_PRICE_PCT": 0.28,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 5,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _lag1_autocorrelation(values):
    if len(values) < 4:
        return 0.0
    left = values[:-1]
    right = values[1:]
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    covariance = sum((x - left_mean) * (y - right_mean)
                     for x, y in zip(left, right))
    left_var = sum((x - left_mean) ** 2 for x in left)
    right_var = sum((y - right_mean) ** 2 for y in right)
    denominator = math.sqrt(left_var * right_var)
    return covariance / denominator if denominator > 1e-12 else 0.0


def detect_s171(rates, tf, dt_bkk, cfg):
    """Trade a closed structural breakout when returns exhibit positive persistence."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(20, int(c["PERSISTENCE_WINDOW"]))
        breakout_lookback = max(5, int(c["BREAKOUT_LOOKBACK"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < window + period + 4 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    closes = [bar["close"] for bar in bars]
    returns = [closes[index] - closes[index - 1]
               for index in range(1, len(closes) - 1)]
    regime_returns = returns[-window:]
    autocorr = _lag1_autocorrelation(regime_returns)
    if autocorr < float(c["AUTOCORR_MIN"]):
        return _wait(f"Returns are not persistent (rho1={autocorr:.2f})")
    net_move = sum(regime_returns)
    min_move = atr * float(c["NET_MOVE_MIN_ATR"])
    if abs(net_move) < min_move:
        return _wait("Persistent regime lacks directional displacement")
    side = 1 if net_move > 0.0 else -1

    breakout = bars[-1]
    breakout_range = breakout["high"] - breakout["low"]
    body = breakout["close"] - breakout["open"]
    if breakout_range <= 0.0 or side * body < atr * float(c["BREAKOUT_BODY_MIN_ATR"]):
        return _wait("No aligned range expansion")
    close_location = (breakout["close"] - breakout["low"]) / breakout_range
    close_edge = float(c["BREAKOUT_CLOSE_EDGE"])
    prior = bars[-breakout_lookback - 1:-1]
    if side > 0:
        structure_broken = breakout["close"] > max(bar["high"] for bar in prior)
        edge_close = close_location >= close_edge
    else:
        structure_broken = breakout["close"] < min(bar["low"] for bar in prior)
        edge_close = close_location <= 1.0 - close_edge
    if not structure_broken or not edge_close:
        return _wait("Expansion did not close through aligned structure")
    volume_min = _quantile(
        [bar["tick_volume"] for bar in bars[-window - 1:-1]],
        c["BREAKOUT_VOLUME_QUANTILE"],
    )
    if breakout["tick_volume"] < volume_min:
        return _wait("Breakout volume is below empirical threshold")

    fraction = float(c["ENTRY_BODY_FRACTION"])
    entry = breakout["close"] - side * fraction * abs(body)
    if (side > 0 and entry >= breakout["close"]) or (side < 0 and entry <= breakout["close"]):
        return _wait("Limit entry is not behind breakout close")
    buffer = atr * float(c["SL_BUFFER_ATR"])
    sl = breakout["low"] - buffer if side > 0 else breakout["high"] + buffer
    entry = round(entry, 2)
    if side > 0:
        sl = math.floor((sl + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((sl - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Persistence-breakout risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Persistence-breakout risk too large versus price ({risk_pct:.2f}%)")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    if side > 0:
        tp = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
        signal = "BUY"
    else:
        tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
        signal = "SELL"
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S171 {signal} Return Persistence {rr:g}R",
        "reason": (f"rho1={autocorr:.2f}, net={net_move / atr:.2f}ATR; "
                   f"high-volume {breakout_lookback}-bar structural breakout"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
