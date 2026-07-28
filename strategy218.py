# -*- coding: utf-8 -*-
"""S218 - Regime-adaptive rollover breakout: drive or fade by recent character, 10R.

The rollover window (04:00-06:00 BKK, NY close / daily settlement) alternates
between "drive" epochs (breakouts continue) and "fade" epochs (breakouts revert)
across market regimes. S206 only wins in drive epochs; S216-style fades only win
in fade epochs. S218 measures the *recent* breakout character causally from the
window it is handed, then trades the rollover drive with S206 logic in a drive
regime, or fades the same breakout in a fade regime. The goal is an edge that
survives every half-year window instead of a single epoch.
"""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 4,
    "SESSION_END_HOUR": 6,
    "RANGE_BARS": 8,
    "BREAK_BODY_MIN_FRACTION": 0.40,
    # Regime measurement over the recent window (all hours, causal).
    # 600 bars is the sweet spot: enough breakout events for a stable regime
    # estimate, short enough not to lag epoch flips. 800 over-filtered (halved
    # the good-epoch return); 400 works too but 600 is best on M5 + M15.
    "REGIME_LOOKBACK": 600,
    "REGIME_HORIZON": 6,
    "REGIME_FOLLOW_ATR": 1.00,
    "REGIME_ADVERSE_ATR": 1.00,
    "REGIME_MIN_EVENTS": 12,
    # Drive-only gate: take S206 drives only when the recent regime is
    # confirmed drive-like (>=0.55 continuation). Fade is disabled by default
    # (FADE_MAX_RATE < 0) because the fade side lost badly in fade epochs;
    # skipping ambiguous/fade regimes is what cuts the multi-year tail in half.
    "DRIVE_MIN_RATE": 0.55,
    "FADE_MAX_RATE": -1.00,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 2.00,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 10.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 3,
}


def _breakout_side(micro_range_bars, breakout, body_min_fraction):
    """Return (+1/-1, range_size) if a directional drive left the range, else None."""
    range_high = max(bar["high"] for bar in micro_range_bars)
    range_low = min(bar["low"] for bar in micro_range_bars)
    range_size = range_high - range_low
    if range_size <= 0.0:
        return None
    body = breakout["close"] - breakout["open"]
    if breakout["close"] > range_high and body > 0.0:
        side = 1
    elif breakout["close"] < range_low and body < 0.0:
        side = -1
    else:
        return None
    if abs(body) < range_size * body_min_fraction:
        return None
    return side, range_size


def _continuation_rate(bars, atr, cfg):
    """Fraction of recent range-breakouts that continued rather than reverted.

    Fully causal: every candidate breakout and its forward outcome lie strictly
    inside the supplied window, before the bar S218 is about to act on.
    """
    range_bars = max(4, int(cfg["RANGE_BARS"]))
    horizon = max(2, int(cfg["REGIME_HORIZON"]))
    body_min = float(cfg["BREAK_BODY_MIN_FRACTION"])
    follow = atr * float(cfg["REGIME_FOLLOW_ATR"])
    adverse = atr * float(cfg["REGIME_ADVERSE_ATR"])
    lookback = max(range_bars + horizon + 4, int(cfg["REGIME_LOOKBACK"]))

    history = bars[-lookback - 1:-1] if len(bars) > lookback + 1 else bars[:-1]
    events = continuations = 0
    index = range_bars
    limit = len(history) - horizon
    while index < limit:
        micro = history[index - range_bars:index]
        breakout = history[index]
        detected = _breakout_side(micro, breakout, body_min)
        if detected is None:
            index += 1
            continue
        side, _ = detected
        entry = breakout["close"]
        outcome = 0
        for step in range(index + 1, index + 1 + horizon):
            high = history[step]["high"]
            low = history[step]["low"]
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
        # Skip past this event's horizon so overlapping windows do not double count.
        index += horizon
    if events == 0:
        return None, 0
    return continuations / events, events


def detect_s218(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Trade the rollover breakout with or against it, per the recent regime."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        range_bars = max(4, int(c["RANGE_BARS"]))
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
        lookback = max(range_bars + 8, int(c["REGIME_LOOKBACK"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = lookback + period + 6
    if rates is None or len(rates) < required or dt_bkk is None:
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
    detected = _breakout_side(micro_range, breakout, float(c["BREAK_BODY_MIN_FRACTION"]))
    if detected is None:
        return _wait("No directional drive out of the micro range")
    drive_side, range_size = detected

    rate, events = _continuation_rate(bars, atr, c)
    if rate is None or events < int(c["REGIME_MIN_EVENTS"]):
        return _wait(f"Not enough regime evidence (events={events})")
    if rate >= float(c["DRIVE_MIN_RATE"]):
        side = drive_side
        mode = "Drive"
    elif rate <= float(c["FADE_MAX_RATE"]):
        side = -drive_side
        mode = "Fade"
    else:
        return _wait(f"Regime is ambiguous (rate={rate:.2f})")

    buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(breakout["close"], 2)
    if side > 0:
        sl = math.floor((breakout["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((breakout["high"] + buffer - 1e-12) * 100.0) / 100.0
    # A fade enters against the breakout bar; its stop sits on the breakout
    # extreme in the trade's risk direction.
    if side > 0 and sl >= entry:
        sl = math.floor((min(breakout["low"], micro_range[-1]["low"]) - buffer
                         + 1e-12) * 100.0) / 100.0
    if side < 0 and sl <= entry:
        sl = math.ceil((max(breakout["high"], micro_range[-1]["high"]) + buffer
                        - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Rollover risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Rollover risk too large versus price")

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
        "pattern": f"S218 {signal} Rollover {mode} {rr:g}R",
        "reason": (f"Rollover breakout in {mode.lower()} regime "
                   f"(cont-rate={rate:.2f}, n={events})"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
