# -*- coding: utf-8 -*-
"""S308 - Counter-bias rollover repricing run, 10R.

S307 showed that selecting S221 momentum runs aligned with an SMA bias improves
the latest window but removes the walk-forward edge at every tested bias
horizon.  Since raw S221 was profitable in both half-years, S308 tests the
causal complementary subset: an expanding three-bar run is accepted only when
it moves against the preceding eight-hour price reference.

The mechanism is not a generic counter-trend trade.  Direction still follows
the expanding run; disagreement with the old reference is interpreted as new
settlement flow strong enough to initiate repricing.  Entry, structural stop,
BE and 10R target are unchanged from S221.
"""

from __future__ import annotations

from strategy119 import _bars
from strategy197 import _wait
from strategy221 import DEFAULT_CFG as S221_DEFAULT_CFG
from strategy221 import detect_s221


DEFAULT_CFG = dict(S221_DEFAULT_CFG)
DEFAULT_CFG.update({
    "HTF_REFERENCE_BARS": 96,
})


def detect_s308(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return an S221 run only when it crosses against the old HTF reference."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        reference_bars = int(c["HTF_REFERENCE_BARS"])
        if reference_bars < 1:
            return _wait("Invalid config: HTF_REFERENCE_BARS must be positive")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < reference_bars + 2:
        return _wait("Not enough history for the HTF reference")

    result = detect_s221(rates, tf=tf, dt_bkk=dt_bkk, cfg=c, **kwargs)
    if result.get("signal") not in ("BUY", "SELL"):
        return result
    try:
        bars = _bars(rates)
        history = bars[-reference_bars - 1:-1]
        reference = sum(bar["close"] for bar in history) / len(history)
        close = bars[-1]["close"]
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")

    if result["signal"] == "BUY" and close >= reference:
        return _wait("BUY run is not a fresh counter-bias repricing")
    if result["signal"] == "SELL" and close <= reference:
        return _wait("SELL run is not a fresh counter-bias repricing")

    signal = result["signal"]
    rr = max(7.0, float(c["TP_RR"]))
    result = dict(result)
    result["pattern"] = f"S308 {signal} Counter-Bias Repricing {rr:g}R"
    result["reason"] = (
        f"{result['reason']}; old HTF reference={reference:.2f}"
    )
    return result
