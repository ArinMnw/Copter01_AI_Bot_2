# -*- coding: utf-8 -*-
"""S306 - Controlled rollover participation drive, 10R.

This is a one-variable ablation of S305.  The participation and higher-timeframe
bias gates are unchanged, but a breakout candle whose body consumes nearly its
entire high-low range is rejected.  Trade-level audits in both six-month
windows showed lower median body/range among TP trades than among non-winners.
The hypothesis is that an almost wickless rollover bar is often a terminal
liquidity burst; a controlled expansion leaves some two-sided auction and has
more continuation capacity.
"""

from __future__ import annotations

import math

from strategy119 import _bars
from strategy197 import _wait
from strategy305 import DEFAULT_CFG as S305_DEFAULT_CFG
from strategy305 import detect_s305


DEFAULT_CFG = dict(S305_DEFAULT_CFG)
DEFAULT_CFG.update({
    # 0 disables the S306 ablation.  A 0.90 ceiling preserves every 2026-H1
    # S304 TP in the feature audit while excluding the most climactic bars.
    "BREAK_BODY_MAX_BAR_FRACTION": 0.90,
})


def detect_s306(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return an S305 rollover drive only when expansion is not climactic."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        ceiling = float(c["BREAK_BODY_MAX_BAR_FRACTION"])
        if not math.isfinite(ceiling) or ceiling < 0.0 or ceiling > 1.0:
            return _wait("Invalid config: body/range ceiling must be in [0, 1]")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")

    result = detect_s305(rates, tf=tf, dt_bkk=dt_bkk, cfg=c, **kwargs)
    if result.get("signal") not in ("BUY", "SELL"):
        return result
    body_fraction = math.nan
    if ceiling > 0.0:
        try:
            breakout = _bars(rates)[-1]
            bar_range = breakout["high"] - breakout["low"]
            if bar_range <= 0.0:
                return _wait("Breakout candle is degenerate")
            body_fraction = abs(breakout["close"] - breakout["open"]) / bar_range
        except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
            return _wait(f"Invalid rates: {exc}")
        if body_fraction > ceiling:
            return _wait(
                f"Drive is climactic ({body_fraction:.2f} body/range > {ceiling:.2f})"
            )

    signal = result["signal"]
    result = dict(result)
    rr = max(7.0, float(c["TP_RR"]))
    result["pattern"] = f"S306 {signal} Controlled Rollover {rr:g}R"
    body_text = "off" if math.isnan(body_fraction) else f"{body_fraction:.2f}"
    result["reason"] = (
        f"{result['reason']}; body/range={body_text}"
    )
    return result
