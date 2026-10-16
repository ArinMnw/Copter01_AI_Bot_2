# -*- coding: utf-8 -*-
"""EA2.1: cost-aware M5 variant of EA2 with M15 trend confirmation."""

from __future__ import annotations

from bisect import bisect_right
from pathlib import Path
import sys


EA2_DIR = Path(__file__).resolve().parents[1] / "ea2"
if str(EA2_DIR) not in sys.path:
    sys.path.insert(0, str(EA2_DIR))

from ea_strategy_2 import (  # noqa: E402
    DEFAULT_CFG as EA2_DEFAULT_CFG,
    LIVE_STATE_VERSION,
    advance_live_state,
    run_backtest,
)


DEFAULT_CFG = dict(EA2_DEFAULT_CFG)
DEFAULT_CFG.update({
    "SL_POINTS": 1200,
    "TP_POINTS": 5000,
    "USE_BREAKEVEN": True,
    "BREAKEVEN_TRIGGER_POINTS": 75,
    "BREAKEVEN_LOCK_POINTS": 25,
    "USE_TRAILING": True,
    "TRAIL_TRIGGER_POINTS": 100,
    "TRAIL_DISTANCE_POINTS": 75,
    "TRAIL_STEP_POINTS": 5,
    "SWING_BARS": 1,
    "BOS_CONFIRM_COUNT": 1,
    "MAX_BARS_LOOKBACK": 500,
    "ONE_TRADE_PER_CYCLE": True,
    "ENTER_ON_BOS_CONFIRM": True,
    "USE_FIB_OB_FILTER": True,
    "OB_SEARCH_MAX_BARS": 5,
    "ENABLE_OB_RETEST_ENTRY": True,
    "OB_MIN_BARS_BEFORE_RETEST": 5,
    "MIN_LEG_POINTS": 200,
    "OB_MAX_BARS_VALID": 100,
    "OB_PREFER_DEEPER_MAX_POINTS": 300,
    "MAX_OPEN_POSITIONS": 1,
    "STRICT_ONE_ENTRY_PER_LEG": True,
    "SESSION_START_HOUR": 0,
    "SESSION_END_HOUR": 24,
    "TIMEFRAME_SECONDS": 300,
    "COOLDOWN_BARS": 3,
    "HTF_EMA_FAST": 20,
    "HTF_EMA_SLOW": 50,
    "HTF_EMA_HISTORY_BARS": 200,
})


def make_entry_filter(htf_rates, *, decision_bar_seconds: int, cfg=None):
    """Return a causal HTF EMA filter combined with an accepted-entry cooldown."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    rows = [] if htf_rates is None else list(htf_rates)
    slow_period = max(2, int(c["HTF_EMA_SLOW"]))
    fast_period = max(1, min(int(c["HTF_EMA_FAST"]), slow_period - 1))
    if len(rows) < slow_period + 5:
        return lambda buy, event_bar, raw_time: False

    times = [int(row["time"]) for row in rows]
    deltas = [b - a for a, b in zip(times, times[1:]) if b > a]
    htf_seconds = min(deltas) if deltas else decision_bar_seconds * 3
    close_times = [raw_time + htf_seconds for raw_time in times]
    closes = [float(row["close"]) for row in rows]
    # Both live and research seed from the same causal, fixed-size window.
    # Extra older history must not silently change a decision's EMA seed.
    history = max(slow_period + 5, int(c["HTF_EMA_HISTORY_BARS"]))
    cache = {}

    def ema_at(idx):
        if idx not in cache:
            window = closes[idx - history + 1:idx + 1]
            fast = slow = window[0]
            for close in window:
                fast += (close - fast) * 2.0 / (fast_period + 1.0)
                slow += (close - slow) * 2.0 / (slow_period + 1.0)
            cache[idx] = (fast, slow)
        return cache[idx]

    cooldown_seconds = max(0, int(c["COOLDOWN_BARS"])) * int(decision_bar_seconds)
    last_accepted_time = -10**18

    def allows(buy: bool, event_bar: int, raw_time: int) -> bool:
        del event_bar
        nonlocal last_accepted_time
        decision_time = int(raw_time) + int(decision_bar_seconds)
        idx = bisect_right(close_times, decision_time) - 1
        if idx < history - 1:
            return False
        fast, slow = ema_at(idx)
        trend_ok = (
            closes[idx] > fast >= slow
            if buy else closes[idx] < fast <= slow
        )
        if not trend_ok or int(raw_time) - last_accepted_time < cooldown_seconds:
            return False
        last_accepted_time = int(raw_time)
        return True

    return allows


def run_backtest_ea2_1(
    bars_raw, htf_rates, cfg=None, *, spread=0.20,
    contract_multiplier=1.0, start_bar=None, timeframe_seconds=300,
):
    """Run EA2.1 with causal HTF confirmation and cooldown."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    c["TIMEFRAME_SECONDS"] = int(timeframe_seconds)
    entry_filter = make_entry_filter(
        htf_rates, decision_bar_seconds=int(timeframe_seconds), cfg=c,
    )
    return run_backtest(
        bars_raw, c, spread=spread, contract_multiplier=contract_multiplier,
        start_bar=start_bar, entry_filter=entry_filter,
    )
