# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S413."""

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
        ("corr010", {"GAP_RESPONSE_ABS_MAX": 0.10}),
        ("corr015", {"GAP_RESPONSE_ABS_MAX": 0.15}),
        ("corr025", {"GAP_RESPONSE_ABS_MAX": 0.25}),
        ("corr035", {"GAP_RESPONSE_ABS_MAX": 0.35}),
        ("corr100", {"GAP_RESPONSE_ABS_MAX": 1.00}),
        ("both", {"ALLOW_SELL": True}),
        ("sell_only", {"ALLOW_BUY": False, "ALLOW_SELL": True}),
        ("ratio108", {"SHAPE_RATIO_MIN": 1.08}),
        ("rise006", {"SHAPE_RISE_MIN": 0.06}),
        ("path006", {"PATH_EFFICIENCY_MIN": 0.06}),
        ("path020", {"PATH_EFFICIENCY_MIN": 0.20}),
        ("session1723", {"SESSION_START_HOUR": 17, "SESSION_END_HOUR": 23}),
        ("session1923", {"SESSION_START_HOUR": 19, "SESSION_END_HOUR": 23}),
    ),
    "finalists": (
        ("base", {}),
        ("corr010", {"GAP_RESPONSE_ABS_MAX": 0.10}),
        ("corr025", {"GAP_RESPONSE_ABS_MAX": 0.25}),
        ("both", {"ALLOW_SELL": True}),
        ("path020", {"PATH_EFFICIENCY_MIN": 0.20}),
        ("session1723", {"SESSION_START_HOUR": 17, "SESSION_END_HOUR": 23}),
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
        summary, _ = backtest(413, months, "M5", 0.20, 0.01, end, 300,
                              cfg, prepared)
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
