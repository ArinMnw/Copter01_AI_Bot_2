# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S411."""

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
        ("fade", {"FADE_IMBALANCE": True}),
        ("align", {"REQUIRE_PATH_ALIGNMENT": True}),
        ("quantile060", {"TAIL_QUANTILE": 0.60}),
        ("quantile080", {"TAIL_QUANTILE": 0.80}),
        ("imbalance005", {"IMBALANCE_ABS_MIN": 0.05}),
        ("imbalance015", {"IMBALANCE_ABS_MIN": 0.15}),
        ("ratio100", {"IMBALANCE_RATIO_MIN": 1.00}),
        ("ratio150", {"IMBALANCE_RATIO_MIN": 1.50}),
        ("rise000", {"IMBALANCE_RISE_MIN": 0.00}),
        ("rise008", {"IMBALANCE_RISE_MIN": 0.08}),
        ("tail100", {"TAIL_RANGE_RATIO_MIN": 1.00}),
        ("tail140", {"TAIL_RANGE_RATIO_MIN": 1.40}),
        ("path000", {"PATH_EFFICIENCY_MIN": 0.00,
                     "NET_MOVE_ATR_MIN": 0.00}),
        ("path012", {"PATH_EFFICIENCY_MIN": 0.12}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("recent028", {"BASELINE_BARS": 84, "RECENT_BARS": 28}),
        ("session1523", {"SESSION_START_HOUR": 15, "SESSION_END_HOUR": 23}),
    ),
    "finalists": (
        ("fade", {"FADE_IMBALANCE": True}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("session1523", {"SESSION_START_HOUR": 15, "SESSION_END_HOUR": 23}),
        ("fade_recent020", {"FADE_IMBALANCE": True,
                            "BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("fade_session1523", {"FADE_IMBALANCE": True,
                              "SESSION_START_HOUR": 15,
                              "SESSION_END_HOUR": 23}),
        ("session1523_recent020", {"SESSION_START_HOUR": 15,
                                   "SESSION_END_HOUR": 23,
                                   "BASELINE_BARS": 60,
                                   "RECENT_BARS": 20}),
    ),
}


def _view(summary):
    return {key: summary[key] for key in (
        "closed", "wins", "win_rate", "net_profit",
        "profit_factor", "max_drawdown",
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
        summary, _ = backtest(411, months, "M5", 0.20, 0.01, end, 300,
                              cfg, prepared)
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
