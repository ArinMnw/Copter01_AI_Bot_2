# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S415."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}
GROUPS = {
    "structure": (
        ("base", {}),
        ("invert", {"INVERT_FORECAST": True}),
        ("ratio080", {"ENTROPY_RATIO_MAX": 0.80}),
        ("ratio100", {"ENTROPY_RATIO_MAX": 1.00}),
        ("drop000", {"ENTROPY_DROP_MIN": 0.00}),
        ("drop008", {"ENTROPY_DROP_MIN": 0.08}),
        ("edge004", {"FORECAST_EDGE_MIN": 0.04}),
        ("edge012", {"FORECAST_EDGE_MIN": 0.12}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("recent028", {"BASELINE_BARS": 84, "RECENT_BARS": 28}),
        ("session0007", {"SESSION_START_HOUR": 0, "SESSION_END_HOUR": 7}),
        ("session0715", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
        ("session1523", {"SESSION_START_HOUR": 15, "SESSION_END_HOUR": 23}),
        ("buy_only", {"ALLOW_SELL": False}),
        ("sell_only", {"ALLOW_BUY": False}),
    ),
    "finalists": (
        ("base", {}),
        ("drop008", {"ENTROPY_DROP_MIN": 0.08}),
        ("edge004", {"FORECAST_EDGE_MIN": 0.04}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("session0715", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
        ("session1523", {"SESSION_START_HOUR": 15, "SESSION_END_HOUR": 23}),
        ("buy_only", {"ALLOW_SELL": False}),
        ("sell_only", {"ALLOW_BUY": False}),
        ("recent020_buy", {"BASELINE_BARS": 60, "RECENT_BARS": 20,
                           "ALLOW_SELL": False}),
        ("recent020_sell", {"BASELINE_BARS": 60, "RECENT_BARS": 20,
                            "ALLOW_BUY": False}),
        ("session1523_buy", {"SESSION_START_HOUR": 15,
                             "SESSION_END_HOUR": 23,
                             "ALLOW_SELL": False}),
        ("session1523_sell", {"SESSION_START_HOUR": 15,
                              "SESSION_END_HOUR": 23,
                              "ALLOW_BUY": False}),
        ("session1523_drop008", {"SESSION_START_HOUR": 15,
                                 "SESSION_END_HOUR": 23,
                                 "ENTROPY_DROP_MIN": 0.08}),
    ),
}


def _view(summary):
    return {key: summary[key] for key in (
        "closed", "wins", "win_rate", "net_profit", "pnl_per_day",
        "pnl_per_month", "profit_factor", "max_drawdown",
    )}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", choices=tuple(WINDOWS), required=True)
    parser.add_argument("--group", choices=tuple(GROUPS), required=True)
    args = parser.parse_args()
    months, end_text = WINDOWS[args.window]
    end = parse_bkk(end_text)
    prepared = prepare_rates(months, "M5", end, 300)
    for name, cfg in GROUPS[args.group]:
        summary, _ = backtest(
            415, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
