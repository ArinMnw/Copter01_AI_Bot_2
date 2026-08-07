# -*- coding: utf-8 -*-
"""Sequential cached active-portfolio interaction audit for S418, following
the same methodology used for S410-S417 (see audit_s417_portfolio.py)."""

from datetime import datetime
import json
from pathlib import Path

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


CACHE_PATH = Path("scratch/portfolio_s417_events.json")
WINDOWS = (
    ("wf", 6, "2026-01-01T00:00:00+07:00"),
    ("h1", 6, "2026-07-01T00:00:00+07:00"),
)
CANDIDATES = {
    "default": {},
}


def _stats(events):
    equity = peak = drawdown = 0.0
    for _, profit in sorted(events):
        equity += profit
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return equity, drawdown, equity / drawdown if drawdown else float("inf")


def main():
    cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    baseline = [
        (datetime.fromisoformat(stamp), float(profit))
        for stamp, profit in cached["baseline"]
    ]
    events = {label: [] for label in CANDIDATES}
    for name, months, end_text in WINDOWS:
        end = parse_bkk(end_text)
        prepared = prepare_rates(months, "M5", end, 300)
        for label, cfg in CANDIDATES.items():
            _, trades = backtest(
                418, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
            )
            events[label].extend(
                (datetime.fromisoformat(trade["exit_time"]), trade["profit"])
                for trade in trades
            )
            print(name, label, len(trades), flush=True)
    print("baseline", _stats(baseline))
    weights = [step / 100.0 for step in range(1, 201)]
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
