# -*- coding: utf-8 -*-
"""Build the frozen active-portfolio cache including optimized S414."""

from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
import json
from pathlib import Path

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


INPUT_PATH = Path("scratch/portfolio_s409_events.json")
OUTPUT_PATH = Path("scratch/portfolio_s414_events.json")
SELECTED_WEIGHT = 7.85
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


def _run_window(window):
    name, months, end_text = window
    end = parse_bkk(end_text)
    prepared = prepare_rates(months, "M5", end, 300)
    _, trades = backtest(
        414, months, "M5", 0.20, 0.01, end, 300, prepared=prepared
    )
    print(name, len(trades), flush=True)
    return trades


def main():
    cached = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    baseline = [
        (datetime.fromisoformat(stamp), float(profit))
        for stamp, profit in cached["baseline"]
    ]
    trades = []
    with ProcessPoolExecutor(max_workers=len(WINDOWS)) as executor:
        for window_trades in executor.map(_run_window, WINDOWS):
            trades.extend(window_trades)
    events = [
        (datetime.fromisoformat(trade["exit_time"]), trade["profit"])
        for trade in trades
    ]
    combined = baseline + [
        (stamp, profit * SELECTED_WEIGHT) for stamp, profit in events
    ]
    OUTPUT_PATH.write_text(
        json.dumps({
            "base_ids": [*cached["base_ids"], 414],
            "windows": cached["windows"],
            "baseline": [
                [stamp.isoformat(), profit] for stamp, profit in combined
            ],
            "s414": [[stamp.isoformat(), profit] for stamp, profit in events],
            "s414_weight": SELECTED_WEIGHT,
        }, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )
    print("standalone", _stats(events), flush=True)
    print("portfolio", _stats(combined), flush=True)
    print("cache", OUTPUT_PATH, flush=True)


if __name__ == "__main__":
    main()
