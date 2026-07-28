# -*- coding: utf-8 -*-
"""S161 - SELL variance-ratio trend-burst pullback, optimized to 40R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "VR_WINDOW": 64,
    "VR_MIN": 1.20,
    "BURST_BARS": 3,
    "BURST_MOVE_MIN_ATR": 0.90,
    "BURST_EFFICIENCY_MIN": 0.80,
    "CLOSE_LOCATION_MIN": 0.72,
    "VOLUME_QUANTILE": 0.65,
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 0.90,
    "MAX_RISK_PRICE_PCT": 0.25,
    "TP_RR": 40.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _variance(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _variance_ratio_two(returns):
    variance_one = _variance(returns)
    if variance_one <= 0.0:
        return 0.0
    two_step = [returns[index] + returns[index - 1]
                for index in range(1, len(returns))]
    return _variance(two_step) / (2.0 * variance_one)


def detect_s161(rates, tf, dt_bkk, cfg):
    """Trade a high-efficiency burst only while the variance ratio shows persistence."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(24, int(c["VR_WINDOW"]))
        burst_bars = max(2, int(c["BURST_BARS"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < window + burst_bars + period + 3 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    returns = [bars[index]["close"] - bars[index - 1]["close"]
               for index in range(1, len(bars))]
    regime_returns = returns[-window - burst_bars:-burst_bars]
    variance_ratio = _variance_ratio_two(regime_returns)
    if variance_ratio < float(c["VR_MIN"]):
        return _wait(f"Variance ratio is not persistent ({variance_ratio:.2f})")
    burst = returns[-burst_bars:]
    burst_move = sum(burst)
    gross_move = sum(abs(value) for value in burst)
    efficiency = abs(burst_move) / gross_move if gross_move > 0.0 else 0.0
    if abs(burst_move) < atr * float(c["BURST_MOVE_MIN_ATR"]):
        return _wait("Recent burst is too small")
    if efficiency < float(c["BURST_EFFICIENCY_MIN"]):
        return _wait("Recent burst is not directionally efficient")

    latest = bars[-1]
    latest_range = latest["high"] - latest["low"]
    latest_body = latest["close"] - latest["open"]
    if latest_range <= 0.0:
        return _wait("Latest range is zero")
    close_location = (latest["close"] - latest["low"]) / latest_range
    location_min = float(c["CLOSE_LOCATION_MIN"])
    if burst_move > 0.0 and latest_body > 0.0 and close_location >= location_min:
        direction = "BUY"
    elif burst_move < 0.0 and latest_body < 0.0 and close_location <= 1.0 - location_min:
        direction = "SELL"
    else:
        return _wait("Latest bar did not confirm the persistent burst")
    if direction == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY branch disabled by robust direction validation")
    if direction == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL branch disabled")

    history = bars[-window - 1:-1]
    volume_min = _quantile([bar["tick_volume"] for bar in history], c["VOLUME_QUANTILE"])
    if latest["tick_volume"] < volume_min:
        return _wait("Confirmation volume is below its empirical threshold")
    fraction = float(c["ENTRY_RANGE_FRACTION"])
    entry = latest["low"] + fraction * latest_range
    if direction == "BUY":
        if entry >= latest["close"]:
            return _wait("BUY limit is not below confirmation close")
        sl = latest["low"] - atr * float(c["SL_BUFFER_ATR"])
    else:
        if entry <= latest["close"]:
            return _wait("SELL limit is not above confirmation close")
        sl = latest["high"] + atr * float(c["SL_BUFFER_ATR"])

    entry = round(entry, 2)
    sl = (math.floor((sl + 1e-12) * 100) / 100 if direction == "BUY"
          else math.ceil((sl - 1e-12) * 100) / 100)
    risk = entry - sl if direction == "BUY" else sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Trend-burst risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Trend-burst risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S161 {direction} Variance-Ratio Burst {rr:g}R",
        "reason": (f"VR(2)={variance_ratio:.2f}, burst={burst_move / atr:+.2f}ATR, "
                   f"efficiency={efficiency:.2f}"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
