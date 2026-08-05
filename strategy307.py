# -*- coding: utf-8 -*-
"""S307 - Rollover momentum run with higher-timeframe alignment, 10R.

S221 is one of the few triggers that was profitable in both half-year windows
and barely overlaps the rolling-range family, but its drawdown was too large.
S303/S304 later established that an approximately eight-hour price bias improves
two distinct rollover break structures.  S307 tests whether that finding
generalizes to S221's independent three-bar expanding-run geometry.

Only one variable is added: the acting close must agree with the SMA of the
preceding HTF_BIAS_BARS closes.  The run, stop, entry, BE and 10R target remain
identical to S221.
"""

from __future__ import annotations

import math

from strategy119 import _bars
from strategy197 import _wait
from strategy221 import DEFAULT_CFG as S221_DEFAULT_CFG
from strategy221 import detect_s221


DEFAULT_CFG = dict(S221_DEFAULT_CFG)
DEFAULT_CFG.update({
    "HTF_BIAS_BARS": 96,
})


def detect_s307(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return an S221 momentum run only when it agrees with the HTF bias."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        bias_bars = int(c["HTF_BIAS_BARS"])
        if bias_bars < 0:
            return _wait("Invalid config: HTF_BIAS_BARS cannot be negative")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < bias_bars + 2:
        return _wait("Not enough history for the higher-timeframe bias")

    result = detect_s221(rates, tf=tf, dt_bkk=dt_bkk, cfg=c, **kwargs)
    if result.get("signal") not in ("BUY", "SELL"):
        return result
    try:
        bars = _bars(rates)
        if bias_bars > 0:
            history = bars[-bias_bars - 1:-1]
            reference = sum(bar["close"] for bar in history) / len(history)
            close = bars[-1]["close"]
            if result["signal"] == "BUY" and close <= reference:
                return _wait("Upward momentum run disagrees with the HTF bias")
            if result["signal"] == "SELL" and close >= reference:
                return _wait("Downward momentum run disagrees with the HTF bias")
        else:
            reference = math.nan
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")

    signal = result["signal"]
    rr = max(7.0, float(c["TP_RR"]))
    result = dict(result)
    result["pattern"] = f"S307 {signal} Rollover Run+HTF {rr:g}R"
    bias_text = "off" if math.isnan(reference) else f"{reference:.2f}"
    result["reason"] = f"{result['reason']}; HTF reference={bias_text}"
    return result
