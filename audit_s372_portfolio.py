# -*- coding: utf-8 -*-
"""Overlap, risk-distance, and incremental portfolio audit for S372."""

from datetime import datetime
from statistics import median

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


BASE_IDS = (346, 349, 351, 355, 358, 359, 361, 362, 363, 365, 366, 367,
            369, 370, 371)
WINDOWS = (
    ("wf", 6, "2026-01-01T00:00:00+07:00"),
    ("h1", 6, "2026-07-01T00:00:00+07:00"),
)


def _portfolio_stats(events):
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
    by_sid = {sid: [] for sid in (*BASE_IDS, 372)}
    h1_trades = {}
    s372_risks = []
    for name, months, end_text in WINDOWS:
        end = parse_bkk(end_text)
        prepared = prepare_rates(months, "M5", end, 300)
        for sid in (*BASE_IDS, 372):
            _, trades = backtest(
                sid,
                months,
                "M5",
                0.20,
                0.01,
                end,
                300,
                prepared=prepared,
            )
            for trade in trades:
                by_sid[sid].append(
                    (datetime.fromisoformat(trade["exit_time"]), trade["profit"])
                )
                if sid == 372:
                    s372_risks.append(abs(trade["entry"] - trade["sl"]))
            if name == "h1":
                h1_trades[sid] = trades
            print(name, sid, len(trades), flush=True)

    s372_times = {trade["signal_time"] for trade in h1_trades[372]}
    overlap = {
        sid: sum(
            trade["signal_time"] in s372_times
            for trade in h1_trades[sid]
        )
        for sid in BASE_IDS
    }
    before = [
        event
        for sid in BASE_IDS
        for event in by_sid[sid]
    ]
    after = before + by_sid[372]
    print("overlap", overlap)
    print(
        "risk",
        {
            "min": min(s372_risks),
            "median": median(s372_risks),
            "max": max(s372_risks),
        },
    )
    print("s372_wf_h1", _portfolio_stats(by_sid[372]))
    print("portfolio_before", _portfolio_stats(before))
    print("portfolio_after", _portfolio_stats(after))


if __name__ == "__main__":
    main()
