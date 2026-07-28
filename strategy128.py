# -*- coding: utf-8 -*-
"""S128 — Asia-to-London Inventory Carry Reclaim.

Measure Asia-session directional inventory, then wait for London to make a
controlled counter-move and reclaim the Asia close.  Entry is a limit at that
close; the Asia midpoint plus ATR buffer invalidates the carry hypothesis.
"""

from __future__ import annotations

import math
from statistics import median

from strategy116 import _normalise_rates, _normalised_delta
from strategy119 import _atr


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "ASIA_START_HOUR": 7,
    "ASIA_END_HOUR": 14,
    "LONDON_HOURS": (14, 15, 16),
    "ASIA_MIN_BARS": 48,
    "ASIA_MOVE_MIN_ATR": 1.20,
    "ASIA_EFFICIENCY_MIN": 0.10,
    "ASIA_DELTA_MIN": 0.03,
    "PULLBACK_MIN_FRACTION": 0.05,
    "PULLBACK_MAX_FRACTION": 0.80,
    "RECLAIM_BUFFER_ATR": 0.05,
    "RECLAIM_BODY_ATR": 0.10,
    "RECLAIM_VOLUME_MULT": 0.75,
    "SL_MID_BUFFER_ATR": 0.20,
    "MAX_RISK_ATR": 4.50,
    "TP_RR": 1.80,
    "BE_RR": 1.00,
    "CANCEL_BARS": 4,
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
            "order_type": "limit",
            "pattern": f"S128 {direction} Asia Inventory Carry",
            "reason": reason, "be_rr": float(cfg["BE_RR"]),
            "cancel_bars": int(cfg["CANCEL_BARS"])}


def detect_s128(rates, tf, dt_bkk, cfg):
    """Detect the first London reclaim after a controlled Asia pullback."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    if rates is None or len(rates) < 100 or dt_bkk is None or dt_bkk.tzinfo is None:
        return _wait("Not enough data or timezone-aware dt_bkk missing")
    try:
        if dt_bkk.hour not in tuple(c["LONDON_HOURS"]):
            return _wait("Outside London carry window")
        bars = _normalise_rates(rates)
        period = int(c["ATR_PERIOD"])
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid input: {exc}")
    day = dt_bkk.replace(hour=0, minute=0, second=0, microsecond=0)
    asia_start = day.replace(hour=int(c["ASIA_START_HOUR"]))
    asia_end = day.replace(hour=int(c["ASIA_END_HOUR"]))
    asia = [bar for bar in bars
            if int(asia_start.timestamp()) <= bar["time"] < int(asia_end.timestamp())]
    london = [bar for bar in bars if int(asia_end.timestamp()) <= bar["time"]]
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
    direction = "BUY" if move > 0.0 else "SELL"
    delta = _normalised_delta(asia)
    if (delta if direction == "BUY" else -delta) < float(c["ASIA_DELTA_MIN"]):
        return _wait("Asia signed volume disagrees")
    latest, previous = london[-1], london[-2]
    min_fraction, max_fraction = (float(c["PULLBACK_MIN_FRACTION"]),
                                  float(c["PULLBACK_MAX_FRACTION"]))
    if not 0.0 <= min_fraction < max_fraction <= 1.0:
        return _wait("Invalid pullback fractions")
    if direction == "BUY":
        pullback = asia_close - min(bar["low"] for bar in london)
        reclaimed = (previous["close"] <= asia_close
                     and latest["close"] >= asia_close + atr * float(c["RECLAIM_BUFFER_ATR"])
                     and latest["close"] - latest["open"] >= atr * float(c["RECLAIM_BODY_ATR"]))
    else:
        pullback = max(bar["high"] for bar in london) - asia_close
        reclaimed = (previous["close"] >= asia_close
                     and latest["close"] <= asia_close - atr * float(c["RECLAIM_BUFFER_ATR"])
                     and latest["open"] - latest["close"] >= atr * float(c["RECLAIM_BODY_ATR"]))
    retrace = pullback / abs(move)
    if not min_fraction <= retrace <= max_fraction or not reclaimed:
        return _wait("No controlled pullback and first Asia-close reclaim")
    baseline_volume = median(bar["tick_volume"] for bar in asia)
    if baseline_volume > 0.0 and latest["tick_volume"] < baseline_volume * float(c["RECLAIM_VOLUME_MULT"]):
        return _wait("Reclaim volume too low")
    midpoint = (asia_open + asia_close) / 2.0
    entry = asia_close
    if direction == "BUY":
        sl = midpoint - atr * float(c["SL_MID_BUFFER_ATR"])
        if entry >= latest["close"]:
            return _wait("BUY limit is not below reclaim close")
        risk = entry - sl
    else:
        sl = midpoint + atr * float(c["SL_MID_BUFFER_ATR"])
        if entry <= latest["close"]:
            return _wait("SELL limit is not above reclaim close")
        risk = sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Risk outside range ({risk / atr:.2f} ATR)")
    reason = (f"{direction} Asia move={move / atr:+.2f}ATR, efficiency={efficiency:.2f}, "
              f"delta={delta:+.2f}, London retrace={retrace:.0%}")
    return _trade(direction, entry, sl, c, reason)
