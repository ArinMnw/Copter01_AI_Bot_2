# -*- coding: utf-8 -*-
"""Breadth falsification probes for S381."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
}

GROUPS = {
    "breadth": (
        ("base", {}),
        ("corr030", {"RECENT_CORRELATION_MAX": 0.30}),
        ("corr050", {"RECENT_CORRELATION_MAX": 0.50}),
        ("drop010", {"CORRELATION_DROP_MIN": 0.10}),
        ("drop000", {"CORRELATION_DROP_MIN": 0.00}),
        ("direction005", {"DIRECTIONAL_VOLUME_MIN": 0.05}),
        ("direction010", {"DIRECTIONAL_VOLUME_MIN": 0.10}),
        ("path005", {"PATH_EFFICIENCY_MIN": 0.05}),
        ("net020", {"NET_MOVE_ATR_MIN": 0.20}),
        ("volume060", {"REJECTION_VOLUME_RATIO_MIN": 0.60}),
        ("volume075", {"REJECTION_VOLUME_RATIO_MIN": 0.75}),
        ("body005", {"REJECTION_BODY_ATR_MIN": 0.05}),
        ("range040", {"REJECTION_RANGE_ATR_MIN": 0.40}),
        ("wick010", {"REJECTION_WICK_FRACTION_MIN": 0.10}),
        ("close045", {"REJECTION_CLOSE_FRACTION": 0.45}),
        ("recent016", {"RECENT_BARS": 16}),
        ("recent024", {"RECENT_BARS": 24}),
    ),
}


def _view(summary):
    return {
        key: summary[key]
        for key in (
            "closed",
            "wins",
            "win_rate",
            "net_profit",
            "profit_factor",
            "max_drawdown",
        )
    }


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
            381,
            months,
            "M5",
            0.20,
            0.01,
            end,
            300,
            cfg,
            prepared,
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
