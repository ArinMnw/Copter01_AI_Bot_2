# -*- coding: utf-8 -*-
"""S118 — Initial-Balance Value-Area Acceptance Retest.

Build an approximate volume profile from the completed session initial
balance, locate POC and the 70% value area, then require two closed candles of
acceptance outside value.  Entry is a limit retest of VAH/VAL.  This is an
independent auction-market alpha and does not call S115–S117.
"""

from __future__ import annotations

import math
from datetime import timedelta
from statistics import median


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "PROFILE_START_HOUR": 14,
    "PROFILE_END_HOUR": 16,
    "TRADE_HOURS": (16, 17, 18, 19, 20, 21, 22),
    "TIME_FILTER_ENABLED": True,
    "PROFILE_MIN_BARS": 18,
    "PROFILE_BINS": 24,
    "VALUE_AREA_PCT": 0.70,
    "ACCEPTANCE_BARS": 2,
    "ACCEPTANCE_BUFFER_ATR": 0.08,
    "ACCEPTANCE_VOLUME_MULT": 0.90,
    "ENTRY_EDGE_ATR": 0.03,
    "SL_POC_BUFFER_ATR": 0.20,
    "MAX_RISK_ATR": 4.00,
    "TP_RR": 1.80,
    "BE_RR": 1.00,
    "CANCEL_BARS": 6,
    "ML_FILTER_ENABLED": False,
    "ML_SCORE_THRESHOLD": 0.55,
    "ML_SYMBOL": "XAUUSD.iux",
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("non-finite numeric value")
    return value


def _normalise(rates):
    bars, previous = [], None
    for raw in rates:
        timestamp = int(_finite(raw["time"]))
        if previous is not None and timestamp <= previous:
            raise ValueError("rates must be chronological")
        previous = timestamp
        bar = {"time": timestamp, "open": _finite(raw["open"]),
               "high": _finite(raw["high"]), "low": _finite(raw["low"]),
               "close": _finite(raw["close"]),
               "tick_volume": max(0.0, _finite(raw["tick_volume"]))}
        if bar["high"] < max(bar["open"], bar["close"], bar["low"]):
            raise ValueError("invalid high")
        if bar["low"] > min(bar["open"], bar["close"], bar["high"]):
            raise ValueError("invalid low")
        bars.append(bar)
    return bars


def _atr(bars, period):
    if len(bars) < period + 1:
        return 0.0
    values = []
    for index in range(len(bars) - period, len(bars)):
        bar, previous_close = bars[index], bars[index - 1]["close"]
        values.append(max(bar["high"] - bar["low"],
                          abs(bar["high"] - previous_close),
                          abs(bar["low"] - previous_close)))
    return sum(values) / len(values)


def _profile(bars, bin_count, value_pct):
    low = min(bar["low"] for bar in bars)
    high = max(bar["high"] for bar in bars)
    width = (high - low) / bin_count
    if width <= 0.0:
        return None
    volumes = [0.0] * bin_count
    for bar in bars:
        first = max(0, min(bin_count - 1, int((bar["low"] - low) / width)))
        last = max(0, min(bin_count - 1, int((bar["high"] - low) / width)))
        count = last - first + 1
        allocation = (bar["tick_volume"] if bar["tick_volume"] > 0.0 else 1.0) / count
        for index in range(first, last + 1):
            volumes[index] += allocation
    poc_index = max(range(bin_count), key=volumes.__getitem__)
    target = sum(volumes) * value_pct
    included = volumes[poc_index]
    lower = upper = poc_index
    while included < target and (lower > 0 or upper < bin_count - 1):
        below = volumes[lower - 1] if lower > 0 else -1.0
        above = volumes[upper + 1] if upper < bin_count - 1 else -1.0
        if above >= below:
            upper += 1
            included += volumes[upper]
        else:
            lower -= 1
            included += volumes[lower]
    poc = low + (poc_index + 0.5) * width
    val = low + lower * width
    vah = low + (upper + 1) * width
    return poc, val, vah, high - low


def _ml_allows(cfg, rates, tf, direction, entry, dt_bkk):
    if not cfg["ML_FILTER_ENABLED"]:
        return True, None
    try:
        import ml_scoring
        probability = float(ml_scoring.score_signal(
            cfg["ML_SYMBOL"], tf, direction, entry, dt_bkk,
            historical_rates=rates,
        ))
    except Exception:
        return False, None
    return probability >= float(cfg["ML_SCORE_THRESHOLD"]), probability


def _trade(direction, entry, sl, cfg, reason):
    entry, sl = round(entry, 2), round(sl, 2)
    risk = entry - sl if direction == "BUY" else sl - entry
    if risk <= 0.0:
        return _wait("Invalid rounded risk")
    rr = max(1.5, float(cfg["TP_RR"]))
    raw_tp = entry + rr * risk if direction == "BUY" else entry - rr * risk
    tp = (math.ceil((raw_tp - 1e-12) * 100.0) / 100.0 if direction == "BUY"
          else math.floor((raw_tp + 1e-12) * 100.0) / 100.0)
    return {"signal": direction, "entry": entry, "sl": sl, "tp": tp,
            "order_type": "limit",
            "pattern": f"S118 {'Bull VAH' if direction == 'BUY' else 'Bear VAL'} Acceptance",
            "reason": reason,
            "be_rr": float(cfg["BE_RR"]) if cfg["BE_RR"] is not None else None,
            "cancel_bars": int(cfg["CANCEL_BARS"]) if cfg["CANCEL_BARS"] is not None else None}


def detect_s118(rates, tf, dt_bkk, cfg):
    """Detect first two-close acceptance outside the completed value area."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        atr_period = int(c["ATR_PERIOD"])
        bins = int(c["PROFILE_BINS"])
        min_bars = int(c["PROFILE_MIN_BARS"])
        acceptance_n = int(c["ACCEPTANCE_BARS"])
        value_pct = float(c["VALUE_AREA_PCT"])
        if atr_period < 1 or bins < 5 or min_bars < 5 or acceptance_n < 2:
            return _wait("Invalid cfg windows")
        if not 0.5 <= value_pct <= 0.95:
            return _wait("VALUE_AREA_PCT must be from 0.5 to 0.95")
    except (KeyError, TypeError, ValueError, OverflowError):
        return _wait("Invalid cfg")
    if rates is None or len(rates) < max(atr_period + 2, min_bars + acceptance_n + 1):
        return _wait("Not enough data")
    if dt_bkk is None or dt_bkk.tzinfo is None:
        return _wait("timezone-aware dt_bkk is required")
    try:
        if c["TIME_FILTER_ENABLED"] and dt_bkk.hour not in tuple(c["TRADE_HOURS"]):
            return _wait("Outside trade hours")
        bars = _normalise(rates)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid input: {exc}")

    session_day = dt_bkk.replace(hour=0, minute=0, second=0, microsecond=0)
    profile_start = session_day.replace(hour=int(c["PROFILE_START_HOUR"]))
    profile_end = session_day.replace(hour=int(c["PROFILE_END_HOUR"]))
    if profile_end <= profile_start:
        profile_end += timedelta(days=1)
    profile_bars = [bar for bar in bars
                    if int(profile_start.timestamp()) <= bar["time"] < int(profile_end.timestamp())]
    if len(profile_bars) < min_bars:
        return _wait(f"Initial balance has only {len(profile_bars)} bars")
    result = _profile(profile_bars, bins, value_pct)
    if result is None:
        return _wait("Profile range is zero")
    poc, val, vah, profile_range = result
    atr = _atr(bars[:-1], atr_period)
    if atr <= 0.0:
        return _wait("ATR is zero")

    accepted = bars[-acceptance_n:]
    before = bars[-acceptance_n - 1]
    baseline = median(bar["tick_volume"] for bar in profile_bars)
    if baseline > 0.0 and accepted[-1]["tick_volume"] < baseline * float(c["ACCEPTANCE_VOLUME_MULT"]):
        return _wait("Acceptance volume is too low")
    buffer = atr * float(c["ACCEPTANCE_BUFFER_ATR"])
    direction = None
    if before["close"] <= vah and all(bar["close"] >= vah + buffer for bar in accepted):
        direction = "BUY"
        entry = vah + atr * float(c["ENTRY_EDGE_ATR"])
        sl = poc - atr * float(c["SL_POC_BUFFER_ATR"])
        if entry >= accepted[-1]["close"]:
            return _wait("BUY limit is not below acceptance close")
    elif before["close"] >= val and all(bar["close"] <= val - buffer for bar in accepted):
        direction = "SELL"
        entry = val - atr * float(c["ENTRY_EDGE_ATR"])
        sl = poc + atr * float(c["SL_POC_BUFFER_ATR"])
        if entry <= accepted[-1]["close"]:
            return _wait("SELL limit is not above acceptance close")
    else:
        return _wait("No first two-close value-area acceptance")
    risk = entry - sl if direction == "BUY" else sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Risk outside allowed range ({risk / atr:.2f} ATR)")
    allowed, probability = _ml_allows(c, rates, tf, direction, entry, dt_bkk)
    if not allowed:
        suffix = "unavailable" if probability is None else f"{probability:.2f}"
        return _wait(f"Blocked by ML ({suffix})")
    reason = (f"{direction} accepted outside value area {val:.2f}-{vah:.2f}; "
              f"POC={poc:.2f}, profile={profile_range / atr:.1f}ATR")
    return _trade(direction, entry, sl, c, reason)
