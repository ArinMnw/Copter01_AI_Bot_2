# -*- coding: utf-8 -*-
"""Cached active-portfolio interaction audit for S409 finalists."""

from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
import json
from pathlib import Path
from statistics import median

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


CACHE_PATH = Path("scratch/portfolio_s408_events.json")
OUTPUT_CACHE_PATH = Path("scratch/portfolio_s409_events.json")
SELECTED_WEIGHT = 3.00
WINDOWS = (
    ("wf", 6, "2026-01-01T00:00:00+07:00"),
    ("h1", 6, "2026-07-01T00:00:00+07:00"),
)
CANDIDATES = {
    "noalign": {"REQUIRE_PATH_ALIGNMENT": False},
    "bias015": {"GAP_BIAS_FRACTION_MIN": 0.15},
    "session0715": {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15},
    "session0715_bias015": {"SESSION_START_HOUR": 7,
                             "SESSION_END_HOUR": 15,
                             "GAP_BIAS_FRACTION_MIN": 0.15},
    "session0715_rr8": {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                         "TP_RR": 8.0},
    "session0715_rr825": {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                           "TP_RR": 8.25},
    "session0715_rr9": {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                         "TP_RR": 9.0},
    "session0715_rr10": {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                          "TP_RR": 10.0},
    "session0715_volume120": {"SESSION_START_HOUR": 7,
                               "SESSION_END_HOUR": 15,
                               "EVENT_VOLUME_RATIO_MIN": 1.20},
    "session0715_fraction070": {"SESSION_START_HOUR": 7,
                                 "SESSION_END_HOUR": 15,
                                 "EVENT_BODY_FRACTION_MIN": 0.70},
}


def _stats(events):
    equity = peak = drawdown = 0.0
    for _, profit in sorted(events):
        equity += profit
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return {"net": equity, "max_drawdown": drawdown,
            "return_dd": equity / drawdown if drawdown else float("inf")}


def _run_window(window):
    name, months, end_text = window
    end = parse_bkk(end_text)
    prepared = prepare_rates(months, "M5", end, 300)
    result = {}
    for label, cfg in CANDIDATES.items():
        _, trades = backtest(409, months, "M5", 0.20, 0.01, end, 300,
                             cfg, prepared)
        result[label] = trades
        print(name, label, len(trades), flush=True)
    return result


def main():
    cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    baseline = [(datetime.fromisoformat(stamp), float(profit))
                for stamp, profit in cached["baseline"]]
    candidates = {label: [] for label in CANDIDATES}
    risks = {label: [] for label in CANDIDATES}
    with ProcessPoolExecutor(max_workers=len(WINDOWS)) as executor:
        for result in executor.map(_run_window, WINDOWS):
            for label, trades in result.items():
                candidates[label].extend(
                    (datetime.fromisoformat(trade["exit_time"]), trade["profit"])
                    for trade in trades
                )
                risks[label].extend(abs(trade["entry"] - trade["sl"])
                                    for trade in trades)
    OUTPUT_CACHE_PATH.write_text(
        json.dumps({
            "base_ids": [*cached["base_ids"], 409],
            "windows": cached["windows"],
            "baseline": [[stamp.isoformat(), profit] for stamp, profit in
                         baseline + [(stamp, profit * SELECTED_WEIGHT) for
                                     stamp, profit in
                                     candidates["session0715_rr825"]]],
            "s409": [[stamp.isoformat(), profit] for stamp, profit in
                     candidates["session0715_rr825"]],
            "s409_weight": SELECTED_WEIGHT,
        }, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8", newline="\n",
    )
    print("cache", str(OUTPUT_CACHE_PATH), flush=True)
    print("portfolio_before", _stats(baseline))
    for label, events in candidates.items():
        values = risks[label]
        print(label, "standalone", _stats(events))
        print(label, "risk", {"min": min(values), "median": median(values),
                              "max": max(values)})
        weights = ((0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 2.00)
                   if label == "session0715_rr825"
                   else (0.25, 0.50, 0.75, 1.00))
        for weight in weights:
            weighted = baseline + [(stamp, profit * weight)
                                   for stamp, profit in events]
            print(label, f"weight_{weight:.2f}", _stats(weighted))


if __name__ == "__main__":
    main()
