# -*- coding: utf-8 -*-
"""Cached active-portfolio interaction audit for S416 finalists."""

from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
import json
from pathlib import Path

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


CACHE_PATH = Path("scratch/portfolio_s414_events.json")
WINDOWS = (
    ("wf", 6, "2026-01-01T00:00:00+07:00"),
    ("h1", 6, "2026-07-01T00:00:00+07:00"),
)
CANDIDATES = {
    "jump090": {"JUMP_RATIO_MIN": 0.90},
    "recent020": {"BASELINE_BARS": 60, "RECENT_BARS": 20},
    "session0715_jump090": {
        "SESSION_START_HOUR": 7,
        "SESSION_END_HOUR": 15,
        "JUMP_RATIO_MIN": 0.90,
    },
    "session0715_recent020": {
        "SESSION_START_HOUR": 7,
        "SESSION_END_HOUR": 15,
        "BASELINE_BARS": 60,
        "RECENT_BARS": 20,
    },
    "jump090_buy": {"JUMP_RATIO_MIN": 0.90, "ALLOW_SELL": False},
    "jump090_sell": {"JUMP_RATIO_MIN": 0.90, "ALLOW_BUY": False},
    "recent020_buy": {
        "BASELINE_BARS": 60, "RECENT_BARS": 20, "ALLOW_SELL": False,
    },
    "recent020_sell": {
        "BASELINE_BARS": 60, "RECENT_BARS": 20, "ALLOW_BUY": False,
    },
}


def _stats(events):
    equity = peak = drawdown = 0.0
    for _, profit in sorted(events):
        equity += profit
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return equity, drawdown, equity / drawdown if drawdown else float("inf")


def _run_window(window):
    name, months, end_text = window
    end = parse_bkk(end_text)
    prepared = prepare_rates(months, "M5", end, 300)
    result = {}
    for label, cfg in CANDIDATES.items():
        _, trades = backtest(
            416, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
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
    events = {label: [] for label in CANDIDATES}
    with ProcessPoolExecutor(max_workers=len(WINDOWS)) as executor:
        for result in executor.map(_run_window, WINDOWS):
            for label, trades in result.items():
                events[label].extend(
                    (datetime.fromisoformat(trade["exit_time"]), trade["profit"])
                    for trade in trades
                )
    print("baseline", _stats(baseline))
    weights = [step / 20.0 for step in range(1, 81)]
    for label, candidate_events in events.items():
        ranked = []
        for weight in weights:
            combined = baseline + [
                (stamp, profit * weight) for stamp, profit in candidate_events
            ]
            ranked.append((*_stats(combined), weight))
        best = max(ranked, key=lambda item: item[2])
        print(label, "standalone", _stats(candidate_events), "best", {
            "net": best[0], "dd": best[1], "ratio": best[2],
            "weight": best[3],
        })


if __name__ == "__main__":
    main()
