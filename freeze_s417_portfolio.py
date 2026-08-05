# -*- coding: utf-8 -*-
"""Build the frozen active-portfolio cache including optimized S417."""

from datetime import datetime
import json
from pathlib import Path

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


INPUT_PATH = Path("scratch/portfolio_s414_events.json")
OUTPUT_PATH = Path("scratch/portfolio_s417_events.json")
SELECTED_WEIGHT = 0.78
WINDOWS = (
    ("wf", 6, "2026-01-01T00:00:00+07:00"),
    ("h1", 6, "2026-07-01T00:00:00+07:00"),
)


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


def main():
    cached = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    baseline = [
        (datetime.fromisoformat(stamp), float(profit))
        for stamp, profit in cached["baseline"]
    ]
    events = []
    for name, months, end_text in WINDOWS:
        end = parse_bkk(end_text)
        prepared = prepare_rates(months, "M5", end, 300)
        _, trades = backtest(
            417, months, "M5", 0.20, 0.01, end, 300, prepared=prepared
        )
        events.extend(
            (datetime.fromisoformat(trade["exit_time"]), trade["profit"])
            for trade in trades
        )
        print(name, len(trades), flush=True)
    combined = baseline + [
        (stamp, profit * SELECTED_WEIGHT) for stamp, profit in events
    ]
    OUTPUT_PATH.write_text(
        json.dumps({
            "base_ids": [*cached["base_ids"], 417],
            "windows": cached["windows"],
            "baseline": [
                [stamp.isoformat(), profit] for stamp, profit in combined
            ],
            "s417": [[stamp.isoformat(), profit] for stamp, profit in events],
            "s417_weight": SELECTED_WEIGHT,
        }, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )
    print("standalone", _stats(events), flush=True)
    print("portfolio", _stats(combined), flush=True)
    print("cache", OUTPUT_PATH, flush=True)


if __name__ == "__main__":
    main()
