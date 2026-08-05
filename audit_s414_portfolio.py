# -*- coding: utf-8 -*-
"""Cached active-portfolio interaction audit for S414 finalists."""

from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
import json
from pathlib import Path
from statistics import median

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


CACHE_PATH = Path("scratch/portfolio_s409_events.json")
WINDOWS = (
    ("wf", 6, "2026-01-01T00:00:00+07:00"),
    ("h1", 6, "2026-07-01T00:00:00+07:00"),
)
CANDIDATES = {
    "base": {},
    "imbalance000": {"FLOW_IMBALANCE_MIN": 0.00},
    "recent020": {"BASELINE_BARS": 60, "RECENT_BARS": 20},
    "session0024": {"SESSION_START_HOUR": 0, "SESSION_END_HOUR": 24},
    "session0024_imb000": {
        "SESSION_START_HOUR": 0,
        "SESSION_END_HOUR": 24,
        "FLOW_IMBALANCE_MIN": 0.00,
    },
    "session1523": {"SESSION_START_HOUR": 15, "SESSION_END_HOUR": 23},
    "session1523_buy": {
        "SESSION_START_HOUR": 15,
        "SESSION_END_HOUR": 23,
        "ALLOW_SELL": False,
    },
    "fade_buy": {"FADE_FLOW": True, "ALLOW_SELL": False},
    "tp9": {"TP_RR": 9.0},
    "session1523_tp8": {
        "SESSION_START_HOUR": 15,
        "SESSION_END_HOUR": 23,
        "TP_RR": 8.0,
    },
    "recent020_tp8": {
        "BASELINE_BARS": 60,
        "RECENT_BARS": 20,
        "TP_RR": 8.0,
    },
}


def _stats(events):
    equity = peak = drawdown = 0.0
    for _, profit in sorted(events):
        equity += profit
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return {
        "net": equity,
        "max_drawdown": drawdown,
        "return_dd": equity / drawdown if drawdown else float("inf"),
    }


def _run_window(window):
    name, months, end_text = window
    end = parse_bkk(end_text)
    prepared = prepare_rates(months, "M5", end, 300)
    result = {}
    for label, cfg in CANDIDATES.items():
        _, trades = backtest(
            414, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        result[label] = trades
        print(name, label, len(trades), flush=True)
    return result


def main():
    cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    baseline = [
        (datetime.fromisoformat(stamp), float(profit))
        for stamp, profit in cached["baseline"]
    ]
    candidates = {label: [] for label in CANDIDATES}
    risks = {label: [] for label in CANDIDATES}
    with ProcessPoolExecutor(max_workers=len(WINDOWS)) as executor:
        for result in executor.map(_run_window, WINDOWS):
            for label, trades in result.items():
                candidates[label].extend(
                    (datetime.fromisoformat(trade["exit_time"]), trade["profit"])
                    for trade in trades
                )
                risks[label].extend(
                    abs(trade["entry"] - trade["sl"]) for trade in trades
                )
    print("portfolio_before", _stats(baseline))
    for label, events in candidates.items():
        values = risks[label]
        print(label, "standalone", _stats(events))
        print(
            label,
            "risk",
            {"min": min(values), "median": median(values), "max": max(values)},
        )
        for weight in (0.05, 0.10, 0.15, 0.20, 0.25, 0.50, 1.00):
            weighted = baseline + [
                (stamp, profit * weight) for stamp, profit in events
            ]
            print(label, f"weight_{weight:.2f}", _stats(weighted))


if __name__ == "__main__":
    main()
