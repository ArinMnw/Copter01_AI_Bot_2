# -*- coding: utf-8 -*-
"""S310 - Binary regime-routed rollover momentum run, 10R.

S309 used a 0.50-0.55 abstention band between fade and drive regimes.  Replay
showed that this band removed the latest window's only 10R winner even though
the routing relationship itself remained useful in the walk-forward window.
S310 tests the single complementary question: classify every sufficiently
sampled regime at one causal 0.55 boundary instead of treating near-boundary
observations as untradeable.

All signal geometry and risk management are inherited from S309.
"""

from __future__ import annotations

from strategy309 import DEFAULT_CFG as S309_DEFAULT_CFG
from strategy309 import detect_s309


DEFAULT_CFG = dict(S309_DEFAULT_CFG)
DEFAULT_CFG.update({
    "DRIVE_MIN_RATE": 0.55,
    "FADE_MAX_RATE": 0.55,
})


def detect_s310(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Route every qualified regime through a single continuation boundary."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    result = detect_s309(rates, tf=tf, dt_bkk=dt_bkk, cfg=c, **kwargs)
    if result.get("signal") in ("BUY", "SELL"):
        result = dict(result)
        result["pattern"] = result["pattern"].replace("S309 ", "S310 ", 1)
    return result
