# -*- coding: utf-8 -*-
"""Cached active-portfolio interaction audit for S407 finalists."""

from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
import json
from pathlib import Path
from statistics import median

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


CACHE_PATH = Path("scratch/portfolio_s405_events.json")
OUTPUT_CACHE_PATH = Path("scratch/portfolio_s407_events.json")
WINDOWS = (
    ("wf", 6, "2026-01-01T00:00:00+07:00"),
    ("h1", 6, "2026-07-01T00:00:00+07:00"),
)
CORE = {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False}
CANDIDATES = {
    "base": CORE,
    "ratio100": {**CORE, "SPREAD_RATIO_MIN": 1.00},
    "path006": {**CORE, "PATH_EFFICIENCY_MIN": 0.06},
    "buffer022": {**CORE, "SL_BUFFER_ATR": 0.22},
    "fraction070": {**CORE, "EVENT_BODY_FRACTION_MIN": 0.70},
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
        _, trades = backtest(407, months, "M5", 0.20, 0.01, end, 300,
                             cfg, prepared)
        result[label] = trades
        print(name, label, len(trades), flush=True)
    return name, result


def main():
    cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    baseline = [(datetime.fromisoformat(stamp), float(profit))
                for stamp, profit in cached["baseline"]]
    candidates = {label: [] for label in CANDIDATES}
    risks = {label: [] for label in CANDIDATES}
    h1_trades = {}
    with ProcessPoolExecutor(max_workers=len(WINDOWS)) as executor:
        for name, result in executor.map(_run_window, WINDOWS):
            for label, trades in result.items():
                candidates[label].extend(
                    (datetime.fromisoformat(trade["exit_time"]), trade["profit"])
                    for trade in trades
                )
                risks[label].extend(abs(trade["entry"] - trade["sl"])
                                    for trade in trades)
                if name == "h1":
                    h1_trades[label] = trades
    OUTPUT_CACHE_PATH.write_text(
        json.dumps({
            "base_ids": [*cached["base_ids"], 407],
            "windows": cached["windows"],
            "baseline": [
                [stamp.isoformat(), profit]
                for stamp, profit in baseline + candidates["base"]
            ],
            "s407": [
                [stamp.isoformat(), profit]
                for stamp, profit in candidates["base"]
            ],
        }, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )
    print("cache", str(OUTPUT_CACHE_PATH), flush=True)
    print("portfolio_before", _stats(baseline))
    for label, events in candidates.items():
        values = risks[label]
        print(label, "standalone", _stats(events))
        print(label, "risk", {"min": min(values), "median": median(values),
                              "max": max(values)})
        for weight in (0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 2.00):
            weighted = baseline + [(stamp, profit * weight)
                                   for stamp, profit in events]
            print(label, f"weight_{weight:.2f}", _stats(weighted))


if __name__ == "__main__":
    main()
