# -*- coding: utf-8 -*-
"""S219 - London/COMEX PM-fix opening-drive breakout, 10R."""

from __future__ import annotations

import math

from datetime import timedelta, timezone

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy218 import _breakout_side, _continuation_rate


BKK = timezone(timedelta(hours=7))


def _session_continuation_rate(bars, atr, cfg):
    """Continuation-rate measured ONLY over breakouts inside this session's hours.

    The market-wide regime measure (S218's) does not transfer across scheduled
    liquidity events — gating PM-fix drives with it turned every window negative.
    This measures the PM-fix window's own character instead: of the past
    in-session breakouts, how many continued rather than reverted. Fully causal —
    every event and its outcome lie strictly before the bar being acted on.
    """
    from datetime import datetime

    range_bars = max(4, int(cfg["RANGE_BARS"]))
    horizon = max(2, int(cfg["REGIME_HORIZON"]))
    body_min = float(cfg["BREAK_BODY_MIN_FRACTION"])
    follow = atr * float(cfg["REGIME_FOLLOW_ATR"])
    adverse = atr * float(cfg["REGIME_ADVERSE_ATR"])
    start_hour = int(cfg["SESSION_START_HOUR"])
    end_hour = int(cfg["SESSION_END_HOUR"])
    lookback = max(range_bars + horizon + 4, int(cfg["SESSION_REGIME_LOOKBACK"]))

    history = bars[-lookback - 1:-1] if len(bars) > lookback + 1 else bars[:-1]
    events = continuations = 0
    index = range_bars
    limit = len(history) - horizon
    while index < limit:
        bar = history[index]
        hour = datetime.fromtimestamp(int(bar["time"]), tz=BKK).hour
        if not start_hour <= hour < end_hour:
            index += 1
            continue
        detected = _breakout_side(history[index - range_bars:index], bar, body_min)
        if detected is None:
            index += 1
            continue
        side, _ = detected
        entry = bar["close"]
        outcome = 0
        for step in range(index + 1, index + 1 + horizon):
            high, low = history[step]["high"], history[step]["low"]
            if side > 0:
                if high - entry >= follow:
                    outcome = 1
                    break
                if entry - low >= adverse:
                    outcome = -1
                    break
            else:
                if entry - low >= follow:
                    outcome = 1
                    break
                if high - entry >= adverse:
                    outcome = -1
                    break
        if outcome != 0:
            events += 1
            if outcome == 1:
                continuations += 1
        index += horizon
    if events == 0:
        return None, 0
    return continuations / events, events


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 21,
    "SESSION_END_HOUR": 23,
    "SESSION_WEEKDAY": -1,
    "RANGE_BARS": 8,
    "BREAK_BODY_MIN_FRACTION": 0.40,
    "BREAK_VOLUME_MIN_RATIO": 0.0,
    "RANGE_MAX_ATR": 0.0,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
    # Optional regime gate (same causal continuation-rate as S218). 0.0 disables.
    "REGIME_LOOKBACK": 600,
    "REGIME_HORIZON": 6,
    "REGIME_FOLLOW_ATR": 1.00,
    "REGIME_ADVERSE_ATR": 1.00,
    "REGIME_MIN_EVENTS": 12,
    "DRIVE_MIN_RATE": 0.0,
    # Session-dedicated regime gate (PM-fix hours only). 0.0 disables.
    "SESSION_REGIME_LOOKBACK": 1800,
    "SESSION_DRIVE_MIN_RATE": 0.0,
    "SESSION_REGIME_MIN_EVENTS": 8,
}


def detect_s219(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade the first directional drive out of the pre-PM-fix micro-range."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        range_bars = max(4, int(c["RANGE_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = range_bars + period + 6
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside rollover session window")
    weekday_filter = int(c.get("SESSION_WEEKDAY", -1))
    if weekday_filter >= 0 and dt_bkk.weekday() != weekday_filter:
        return _wait("Outside configured rollover weekday")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    micro_range = bars[-range_bars - 1:-1]
    range_high = max(bar["high"] for bar in micro_range)
    range_low = min(bar["low"] for bar in micro_range)
    range_size = range_high - range_low
    if range_size <= 0.0:
        return _wait("Micro range is degenerate")

    breakout = bars[-1]
    body = breakout["close"] - breakout["open"]
    if breakout["close"] > range_high and body > 0.0:
        side = 1
    elif breakout["close"] < range_low and body < 0.0:
        side = -1
    else:
        return _wait("No directional drive out of the micro range")
    if abs(body) < range_size * float(c["BREAK_BODY_MIN_FRACTION"]):
        return _wait("Drive body is too small versus the micro range")
    drive_floor = float(c.get("DRIVE_MIN_RATE", 0.0))
    if drive_floor > 0.0:
        rate, events = _continuation_rate(bars, atr, c)
        if rate is None or events < int(c["REGIME_MIN_EVENTS"]):
            return _wait(f"Not enough regime evidence (events={events})")
        if rate < drive_floor:
            return _wait(f"Market regime is not drive-like (rate={rate:.2f})")
    session_floor = float(c.get("SESSION_DRIVE_MIN_RATE", 0.0))
    session_rate = None
    if session_floor > 0.0:
        session_rate, session_events = _session_continuation_rate(bars, atr, c)
        if (session_rate is None
                or session_events < int(c["SESSION_REGIME_MIN_EVENTS"])):
            return _wait(f"Not enough PM-fix regime evidence (n={session_events})")
        if session_rate < session_floor:
            return _wait(f"PM-fix session is not drive-like (rate={session_rate:.2f})")
    range_cap = float(c["RANGE_MAX_ATR"])
    if range_cap > 0.0 and range_size > atr * range_cap:
        return _wait("Micro range is not compressed enough")
    volume_ratio_floor = float(c["BREAK_VOLUME_MIN_RATIO"])
    if volume_ratio_floor > 0.0:
        mean_volume = sum(bar["tick_volume"] for bar in micro_range) / len(micro_range)
        if mean_volume <= 0.0 or breakout["tick_volume"] < mean_volume * volume_ratio_floor:
            return _wait("Drive lacks volume expansion")

    buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        entry = breakout["close"]
        sl = math.floor((breakout["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        entry = breakout["close"]
        sl = math.ceil((breakout["high"] + buffer - 1e-12) * 100.0) / 100.0
    entry = round(entry, 2)
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Drive risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Drive risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    if side > 0:
        signal = "BUY"
        tp = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
    else:
        signal = "SELL"
        tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S219 {signal} PM-Fix Drive {rr:g}R",
        "reason": (f"Drive out of {range_size:.2f} micro range at rollover; "
                   f"risk={risk:.2f}"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
