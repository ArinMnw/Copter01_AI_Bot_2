# -*- coding: utf-8 -*-
"""S303 - Rollover opening-range breakout gated by higher-timeframe bias, 10R.

Built on the only validated edge in this project rather than another statistical
gate: the rollover clock (04-06 BKK) AND a structural break are both required
(S212 removed the clock and lost; S223 removed the break and lost -35/-24 in the
same window where S206 made +412/+137). S224 established that an *anchored*
opening range with a tight-range filter is the best form of that break
(12m +328.68, return/DD 16.6).

S303 adds the third ingredient never tried at rollover: a higher-timeframe
directional bias. Only breaks that agree with the ~24h trend (close vs the SMA
of the last HTF_BIAS_BARS M5 closes) are taken. The bet is that settlement flow
which pushes price out of the session range *with* the prevailing daily trend
continues, while counter-trend breaks are the ones that fail. Everything else is
identical to S224 so the bias filter is the only variable.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from strategy119 import _atr, _bars
from strategy197 import _wait


BKK = timezone(timedelta(hours=7))

DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 4,
    "SESSION_END_HOUR": 6,
    # Bars of the session that define the anchored opening range.
    "OR_BARS": 6,
    "BREAK_BODY_MIN_FRACTION": 0.40,
    # Tight-range requirement — the classic ORB form (compression then
    # expansion). 2.0 is the value that clears both validation windows with the
    # best return/DD (12m +328.68, worst DD 19.78, ratio 16.6 vs 4.8 unfiltered).
    # Below ~1.5 the 6-bar range is essentially never that tight and n collapses.
    "OR_MAX_ATR": 2.0,          # 0 disables the filter
    # Higher-timeframe bias: require close on the correct side of the SMA of the
    # last N M5 closes. 96 (~8h) chosen on the walk-forward window, which is
    # decisive here: 2026-H1 is flat across 96/144/288/576 (+277..+282) while
    # 2025-H2 clearly prefers 96 (+36.14 vs +8.08/+15.67/+23.33) with the lowest
    # DD too. 0 disables the filter.
    "HTF_BIAS_BARS": 96,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _todays_session_bars(bars, day, start_hour, end_hour):
    """Bars of `day`'s session, oldest first (excludes nothing; caller slices)."""
    out = []
    for bar in bars:
        moment = datetime.fromtimestamp(int(bar["time"]), tz=BKK)
        if moment.date() == day and start_hour <= moment.hour < end_hour:
            out.append(bar)
    return out


def detect_s303(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade a close beyond the rollover session's anchored opening range."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        or_bars = max(2, int(c["OR_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < period + or_bars + 6 or dt_bkk is None:
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

    # Everything before the acting bar, from today's session only.
    prior = _todays_session_bars(bars[:-1], dt_bkk.date(), start_hour, end_hour)
    if len(prior) < or_bars:
        return _wait(f"Opening range not complete ({len(prior)}/{or_bars} bars)")
    opening = prior[:or_bars]
    or_high = max(bar["high"] for bar in opening)
    or_low = min(bar["low"] for bar in opening)
    or_size = or_high - or_low
    if or_size <= 0.0:
        return _wait("Opening range is degenerate")
    or_cap = float(c["OR_MAX_ATR"])
    if or_cap > 0.0 and or_size > atr * or_cap:
        return _wait("Opening range is too wide")

    # Only the first break counts: if a later session bar already closed beyond
    # the range, today's move is no longer a fresh break.
    for bar in prior[or_bars:]:
        if bar["close"] > or_high or bar["close"] < or_low:
            return _wait("Opening range was already broken today")

    breakout = bars[-1]
    body = breakout["close"] - breakout["open"]
    if breakout["close"] > or_high and body > 0.0:
        side = 1
    elif breakout["close"] < or_low and body < 0.0:
        side = -1
    else:
        return _wait("No fresh close beyond the opening range")
    bar_range = breakout["high"] - breakout["low"]
    if bar_range <= 0.0 or abs(body) < bar_range * float(
            c["BREAK_BODY_MIN_FRACTION"]):
        return _wait("Break bar lacks body conviction")

    bias_bars = int(c.get("HTF_BIAS_BARS", 0) or 0)
    if bias_bars > 0:
        history = bars[-bias_bars - 1:-1]
        if len(history) < bias_bars:
            return _wait("Not enough history for the higher-timeframe bias")
        reference = sum(bar["close"] for bar in history) / len(history)
        if side > 0 and breakout["close"] <= reference:
            return _wait("Upward break disagrees with the higher-timeframe bias")
        if side < 0 and breakout["close"] >= reference:
            return _wait("Downward break disagrees with the higher-timeframe bias")

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
        return _wait(f"ORB risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("ORB risk too large versus price")

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
        "pattern": f"S303 {signal} Rollover ORB+HTF {rr:g}R",
        "reason": (f"First close beyond the {or_size:.2f} anchored opening "
                   "range, aligned with the higher-timeframe bias"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
