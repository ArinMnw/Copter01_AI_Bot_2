# -*- coding: utf-8 -*-
"""S309 - Regime-routed rollover momentum run, 10R.

S307 (HTF-aligned run) won the latest fade window but failed 2025-H2.  Its
causal complement S308 (counter-bias repricing run) produced the opposite
profile: weak recently, strong in 2025-H2.  S309 routes the common S221
expanding-run trigger using only prior range-break outcomes:

* fade regime: accept HTF-aligned runs, where agreement supplies persistence;
* drive regime: accept counter-bias runs, interpreted as fresh repricing;
* ambiguous regime: do not trade.

The continuation-rate estimator is inherited from S218 and only evaluates
events whose complete outcome horizon precedes the acting bar.  Entry, stop,
BE and 10R target remain S221's.
"""

from __future__ import annotations

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy218 import _continuation_rate
from strategy221 import DEFAULT_CFG as S221_DEFAULT_CFG
from strategy221 import detect_s221


DEFAULT_CFG = dict(S221_DEFAULT_CFG)
DEFAULT_CFG.update({
    "HTF_REFERENCE_BARS": 96,
    "RANGE_BARS": 8,
    "BREAK_BODY_MIN_FRACTION": 0.40,
    "REGIME_LOOKBACK": 600,
    "REGIME_HORIZON": 6,
    "REGIME_FOLLOW_ATR": 1.00,
    "REGIME_ADVERSE_ATR": 1.00,
    "REGIME_MIN_EVENTS": 12,
    "DRIVE_MIN_RATE": 0.55,
    "FADE_MAX_RATE": 0.50,
})


def detect_s309(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Route an expanding rollover run by prior continuation character."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        reference_bars = int(c["HTF_REFERENCE_BARS"])
        regime_lookback = int(c["REGIME_LOOKBACK"])
        min_events = int(c["REGIME_MIN_EVENTS"])
        drive_floor = float(c["DRIVE_MIN_RATE"])
        fade_ceiling = float(c["FADE_MAX_RATE"])
        if reference_bars < 1 or regime_lookback < 20 or min_events < 1:
            return _wait("Invalid config: regime/reference windows are too small")
        if fade_ceiling > drive_floor:
            return _wait("Invalid config: FADE_MAX_RATE exceeds DRIVE_MIN_RATE")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(reference_bars + 2, regime_lookback + 2)
    if rates is None or len(rates) < required:
        return _wait(f"Not enough data for regime router ({len(rates) if rates is not None else 0}/{required})")

    result = detect_s221(rates, tf=tf, dt_bkk=dt_bkk, cfg=c, **kwargs)
    if result.get("signal") not in ("BUY", "SELL"):
        return result
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-1], int(c["ATR_PERIOD"]))
        if atr <= 0.0:
            return _wait("ATR is zero")
        rate, events = _continuation_rate(bars, atr, c)
        if rate is None or events < min_events:
            return _wait(f"Not enough regime evidence (events={events})")
        history = bars[-reference_bars - 1:-1]
        reference = sum(bar["close"] for bar in history) / len(history)
        close = bars[-1]["close"]
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates or config: {exc}")

    signal = result["signal"]
    aligned = (
        (signal == "BUY" and close > reference)
        or (signal == "SELL" and close < reference)
    )
    if rate <= fade_ceiling:
        regime = "Fade"
        if not aligned:
            return _wait("Fade regime requires an HTF-aligned momentum run")
    elif rate >= drive_floor:
        regime = "Drive"
        if aligned:
            return _wait("Drive regime requires a counter-bias repricing run")
    else:
        return _wait(f"Regime is ambiguous (rate={rate:.2f})")

    rr = max(7.0, float(c["TP_RR"]))
    result = dict(result)
    result["pattern"] = f"S309 {signal} {regime}-Routed Run {rr:g}R"
    result["reason"] = (
        f"{result['reason']}; {regime.lower()} regime rate={rate:.2f} "
        f"(n={events}), HTF reference={reference:.2f}"
    )
    return result
