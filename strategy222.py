# -*- coding: utf-8 -*-
"""S222 - Rollover drive gated by session-relative anomaly, 10R.

Two things are new here versus the rest of this campaign.

1. **Session-relative normalization.** Every previous filter compared a bar to
   its recent neighbours (ATR, quantiles of the last N bars). This one compares
   the rollover session *to the same session on prior days*: is today's 04-06
   window unusually active for a 04-06 window? A rollover that is busier than
   its own history is evidence of real settlement flow rather than quiet drift,
   which is the mechanism S206 is trying to harvest in the first place.

2. **Designed for return/DD, not just net.** S221 passed the dual-window bar but
   failed on risk (return/DD 2.4) because its losers were full-R stops. The
   high-ratio strategy in this project (S202, ratio ~90) wins because an
   aggressive breakeven turns most losers into scratches. S222 therefore ships
   with BE at 0.55R from the start rather than 1.0R.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy218 import _breakout_side


BKK = timezone(timedelta(hours=7))

DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 4,
    "SESSION_END_HOUR": 6,
    "RANGE_BARS": 8,
    "BREAK_BODY_MIN_FRACTION": 0.40,
    # Session-relative anomaly gate.
    "SESSION_HISTORY_DAYS": 5,
    "ANOMALY_MIN_RATIO": 1.15,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 0.55,
    "CANCEL_BARS": 3,
}


def _session_ranges_by_day(bars, start_hour, end_hour):
    """High-low range of the session window, per calendar day (BKK)."""
    per_day = {}
    for bar in bars:
        moment = datetime.fromtimestamp(int(bar["time"]), tz=BKK)
        if not start_hour <= moment.hour < end_hour:
            continue
        day = moment.date()
        high, low = per_day.get(day, (bar["high"], bar["low"]))
        per_day[day] = (max(high, bar["high"]), min(low, bar["low"]))
    return {day: hi - lo for day, (hi, lo) in per_day.items()}


def detect_s222(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade the rollover drive only when the session is unusually active."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        range_bars = max(4, int(c["RANGE_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
        history_days = max(2, int(c["SESSION_HISTORY_DAYS"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < range_bars + period + 6 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside rollover session window")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    micro_range = bars[-range_bars - 1:-1]
    breakout = bars[-1]
    detected = _breakout_side(micro_range, breakout,
                              float(c["BREAK_BODY_MIN_FRACTION"]))
    if detected is None:
        return _wait("No directional drive out of the micro range")
    side, range_size = detected

    # Session-relative anomaly: today's session range so far (all bars strictly
    # before the acting bar are already in `bars`) versus prior completed days.
    ranges = _session_ranges_by_day(bars, start_hour, end_hour)
    today = dt_bkk.date()
    today_range = ranges.get(today)
    prior = [value for day, value in ranges.items() if day < today and value > 0.0]
    if today_range is None or len(prior) < history_days:
        return _wait(f"Not enough session history (days={len(prior)})")
    prior = sorted(prior)[-history_days:]
    reference = sorted(prior)[len(prior) // 2]
    if reference <= 0.0:
        return _wait("Session reference range is zero")
    ratio = today_range / reference
    if ratio < float(c["ANOMALY_MIN_RATIO"]):
        return _wait(f"Session is not unusually active (ratio={ratio:.2f})")

    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(breakout["close"], 2)
    if side > 0:
        sl = math.floor((breakout["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((breakout["high"] + buffer - 1e-12) * 100.0) / 100.0
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
        "pattern": f"S222 {signal} Rollover Anomaly Drive {rr:g}R",
        "reason": (f"Rollover session {ratio:.2f}x its own {history_days}-day "
                   "median range; drive out of the micro range"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
