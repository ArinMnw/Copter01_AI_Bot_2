# -*- coding: utf-8 -*-
"""Portfolio-selectivity falsification for S403 dominance thresholds."""

from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


BASE_IDS = (346, 349, 351, 355, 358, 359, 361, 362, 363, 365, 366, 367,
            369, 370, 371, 372, 373, 374, 375, 376, 378, 379, 380, 382, 383,
            384, 385, 386, 387, 389, 393, 394, 396, 398, 399, 401, 402)
CANDIDATES = {
    "d066": {},
    "d070": {"DOMINANCE_MIN": 0.70},
    "d074": {"DOMINANCE_MIN": 0.74},
}
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


def _events(trades):
    return [
        (datetime.fromisoformat(trade["exit_time"]), trade["profit"])
        for trade in trades
    ]


def _run_window(window):
    name, months, end_text = window
    end = parse_bkk(end_text)
    prepared = prepare_rates(months, "M5", end, 300)
    base = {}
    for sid in BASE_IDS:
        _, trades = backtest(
            sid, months, "M5", 0.20, 0.01, end, 300, prepared=prepared
        )
        base[sid] = trades
        print(name, sid, len(trades), flush=True)
    candidates = {}
    for label, cfg in CANDIDATES.items():
        _, trades = backtest(
            403, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        candidates[label] = trades
        print(name, label, len(trades), flush=True)
    return base, candidates


def main():
    baseline = []
    candidates = {label: [] for label in CANDIDATES}
    with ProcessPoolExecutor(max_workers=len(WINDOWS)) as executor:
        for base_result, candidate_result in executor.map(_run_window, WINDOWS):
            for trades in base_result.values():
                baseline.extend(_events(trades))
            for label, trades in candidate_result.items():
                candidates[label].extend(_events(trades))

    print("portfolio_before", _stats(baseline))
    for label, candidate_events in candidates.items():
        print(label, "standalone", _stats(candidate_events))
        for weight in (0.25, 0.50, 0.75, 1.00):
            weighted = baseline + [
                (stamp, profit * weight) for stamp, profit in candidate_events
            ]
            print(label, f"weight_{weight:.2f}", _stats(weighted))


if __name__ == "__main__":
    main()
