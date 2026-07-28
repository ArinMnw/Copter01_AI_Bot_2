# -*- coding: utf-8 -*-
"""S130 — London Liquidation of Asia Inventory.

Trade the complementary failure state of S128: a directional Asia session is
invalidated when London closes through the Asia midpoint for the first time.
The midpoint becomes the limit retest and the Asia close anchors structural SL.
"""

from __future__ import annotations

import math
from statistics import median

from strategy116 import _normalise_rates, _normalised_delta
from strategy119 import _atr


DEFAULT_CFG = {
    "ATR_PERIOD": 14, "ASIA_START_HOUR": 7, "ASIA_END_HOUR": 14,
    "LONDON_HOURS": (14, 15, 16), "ASIA_MIN_BARS": 48,
    "ASIA_MOVE_MIN_ATR": 1.20, "ASIA_EFFICIENCY_MIN": 0.10,
    "ASIA_DELTA_MIN": 0.03, "MID_BREAK_BUFFER_ATR": 0.05,
    "BREAK_BODY_ATR": 0.10, "BREAK_VOLUME_MULT": 0.75,
    "SL_CLOSE_BUFFER_ATR": 0.20, "MAX_RISK_ATR": 4.50,
    "TP_RR": 1.80, "BE_RR": 1.00, "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _trade(direction, entry, sl, cfg, reason):
    entry, sl = round(entry, 2), round(sl, 2)
    risk = entry - sl if direction == "BUY" else sl - entry
    if risk <= 0.0:
        return _wait("Invalid rounded risk")
    rr = max(1.5, float(cfg["TP_RR"]))
    raw = entry + rr * risk if direction == "BUY" else entry - rr * risk
    tp = (math.ceil((raw - 1e-12) * 100) / 100 if direction == "BUY"
          else math.floor((raw + 1e-12) * 100) / 100)
    return {"signal": direction, "entry": entry, "sl": sl, "tp": tp,
            "order_type": "limit", "pattern": f"S130 {direction} Asia Liquidation",
            "reason": reason, "be_rr": float(cfg["BE_RR"]),
            "cancel_bars": int(cfg["CANCEL_BARS"])}


def detect_s130(rates, tf, dt_bkk, cfg):
    """Detect the first London close through a directional Asia midpoint."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    if rates is None or len(rates) < 100 or dt_bkk is None or dt_bkk.tzinfo is None:
        return _wait("Not enough data or timezone-aware dt_bkk missing")
    try:
        if dt_bkk.hour not in tuple(c["LONDON_HOURS"]):
            return _wait("Outside London liquidation window")
        bars = _normalise_rates(rates)
        period = int(c["ATR_PERIOD"])
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid input: {exc}")
    day = dt_bkk.replace(hour=0, minute=0, second=0, microsecond=0)
    start = day.replace(hour=int(c["ASIA_START_HOUR"]))
    end = day.replace(hour=int(c["ASIA_END_HOUR"]))
    asia = [bar for bar in bars if int(start.timestamp()) <= bar["time"] < int(end.timestamp())]
    london = [bar for bar in bars if bar["time"] >= int(end.timestamp())]
    if len(asia) < int(c["ASIA_MIN_BARS"]) or len(london) < 2:
        return _wait("Session bars are incomplete")
    atr = _atr(bars[:-1], period)
    if atr <= 0.0:
        return _wait("ATR is zero")
    asia_open, asia_close = asia[0]["open"], asia[-1]["close"]
    move = asia_close - asia_open
    path = sum(abs(asia[index]["close"] - asia[index - 1]["close"])
               for index in range(1, len(asia)))
    efficiency = abs(move) / path if path > 0.0 else 0.0
    if abs(move) < atr * float(c["ASIA_MOVE_MIN_ATR"]) or efficiency < float(c["ASIA_EFFICIENCY_MIN"]):
        return _wait("Asia inventory is not directional")
    delta = _normalised_delta(asia)
    if (delta if move > 0.0 else -delta) < float(c["ASIA_DELTA_MIN"]):
        return _wait("Asia signed volume disagrees")
    midpoint = (asia_open + asia_close) / 2.0
    latest, previous = london[-1], london[-2]
    buffer = atr * float(c["MID_BREAK_BUFFER_ATR"])
    min_body = atr * float(c["BREAK_BODY_ATR"])
    if move > 0.0:
        direction = "SELL"
        crossed = (previous["close"] >= midpoint and latest["close"] <= midpoint - buffer
                   and latest["open"] - latest["close"] >= min_body)
        entry, sl = midpoint, asia_close + atr * float(c["SL_CLOSE_BUFFER_ATR"])
        valid_limit = entry > latest["close"]
    else:
        direction = "BUY"
        crossed = (previous["close"] <= midpoint and latest["close"] >= midpoint + buffer
                   and latest["close"] - latest["open"] >= min_body)
        entry, sl = midpoint, asia_close - atr * float(c["SL_CLOSE_BUFFER_ATR"])
        valid_limit = entry < latest["close"]
    if not crossed or not valid_limit:
        return _wait("No first London break of Asia midpoint")
    volume_base = median(bar["tick_volume"] for bar in asia)
    if volume_base > 0.0 and latest["tick_volume"] < volume_base * float(c["BREAK_VOLUME_MULT"]):
        return _wait("Midpoint-break volume too low")
    risk = entry - sl if direction == "BUY" else sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Risk outside range ({risk / atr:.2f} ATR)")
    reason = (f"{direction} liquidates Asia move={move / atr:+.2f}ATR after first "
              f"midpoint break; efficiency={efficiency:.2f}, delta={delta:+.2f}")
    return _trade(direction, entry, sl, c, reason)
