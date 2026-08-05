# -*- coding: utf-8 -*-
"""Breadth falsification probes for S379."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
}

GROUPS = {
    "risk": tuple(
        (
            f"buffer{int(buffer * 100):03d}",
            {
                "CLUSTER_STRENGTH_MIN": 0.40,
                "SL_BUFFER_ATR": buffer,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        )
        for buffer in (0.04, 0.08, 0.12, 0.16, 0.20)
    ),
    "cluster_fine": tuple(
        (
            f"cluster{int(cluster * 100):03d}",
            {
                "CLUSTER_STRENGTH_MIN": cluster,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        )
        for cluster in (0.36, 0.38, 0.40, 0.42, 0.44)
    ),
    "cluster_local": tuple(
        (
            f"cluster{int(cluster * 100):03d}",
            {
                "CLUSTER_STRENGTH_MIN": cluster,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        )
        for cluster in (0.20, 0.30, 0.35, 0.40, 0.45, 0.50)
    ),
    "refine": (
        (
            "base",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "cluster040",
            {
                "CLUSTER_STRENGTH_MIN": 0.40,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "cluster050",
            {
                "CLUSTER_STRENGTH_MIN": 0.50,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "cluster070",
            {
                "CLUSTER_STRENGTH_MIN": 0.70,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "expansion010",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "CLUSTER_EXPANSION_MIN": 0.10,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "expansion020",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "CLUSTER_EXPANSION_MIN": 0.20,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "expansion040",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "CLUSTER_EXPANSION_MIN": 0.40,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "sign010",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "SIGN_IMBALANCE_MIN": 0.10,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "path015",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "PATH_EFFICIENCY_MIN": 0.15,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "close065",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "EVENT_CLOSE_FRACTION": 0.65,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "close085",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "EVENT_CLOSE_FRACTION": 0.85,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "baseline048",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "BASELINE_BARS": 48,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "baseline096",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "BASELINE_BARS": 96,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "recent020",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "RECENT_BARS": 20,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "recent028",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "RECENT_BARS": 28,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
    ),
    "payoff": (
        ("cluster060", {"CLUSTER_STRENGTH_MIN": 0.60}),
        (
            "buy_only",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "ALLOW_SELL": False,
            },
        ),
        (
            "sell_only",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "ALLOW_BUY": False,
            },
        ),
        (
            "rr8",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "TP_RR": 8.0,
            },
        ),
        (
            "rr9",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "TP_RR": 9.0,
            },
        ),
        (
            "rr10",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "TP_RR": 10.0,
            },
        ),
        (
            "be001",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "BE_RR": 0.01,
            },
        ),
        (
            "be002",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "BE_RR": 0.02,
            },
        ),
        (
            "be008",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "BE_RR": 0.08,
            },
        ),
        (
            "be012",
            {
                "CLUSTER_STRENGTH_MIN": 0.60,
                "BE_RR": 0.12,
            },
        ),
    ),
    "focus": (
        ("base", {}),
        ("cluster060", {"CLUSTER_STRENGTH_MIN": 0.60}),
        ("cluster080", {"CLUSTER_STRENGTH_MIN": 0.80}),
        ("recent020", {"RECENT_BARS": 20}),
        (
            "cluster080_recent020",
            {
                "CLUSTER_STRENGTH_MIN": 0.80,
                "RECENT_BARS": 20,
            },
        ),
    ),
    "breadth": (
        ("base", {}),
        ("cluster060", {"CLUSTER_STRENGTH_MIN": 0.60}),
        ("cluster080", {"CLUSTER_STRENGTH_MIN": 0.80}),
        ("expansion000", {"CLUSTER_EXPANSION_MIN": 0.00}),
        ("expansion015", {"CLUSTER_EXPANSION_MIN": 0.15}),
        ("sign010", {"SIGN_IMBALANCE_MIN": 0.10}),
        ("path010", {"PATH_EFFICIENCY_MIN": 0.10}),
        ("net025", {"NET_MOVE_ATR_MIN": 0.25}),
        ("body035", {"EVENT_BODY_ATR_MIN": 0.35}),
        ("range060", {"EVENT_RANGE_ATR_MIN": 0.60}),
        ("fraction045", {"EVENT_BODY_FRACTION_MIN": 0.45}),
        ("close060", {"EVENT_CLOSE_FRACTION": 0.60}),
        ("baseline048", {"BASELINE_BARS": 48}),
        ("recent020", {"RECENT_BARS": 20}),
        ("recent030", {"RECENT_BARS": 30}),
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
            379,
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
