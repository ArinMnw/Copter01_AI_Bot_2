# -*- coding: utf-8 -*-
"""Cross-window robustness probes for S325."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = (
    ("2m", 2, "2026-07-20T00:00:00+07:00"),
    ("h1", 6, "2026-07-01T00:00:00+07:00"),
    ("wf", 6, "2026-01-01T00:00:00+07:00"),
)


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
    parser.add_argument(
        "--probe",
        help="Run one named probe; omit to list available probes",
    )
    args = parser.parse_args()
    probes = (
        ("buy", {"ALLOW_SELL": False}),
        ("buy_rr7", {"ALLOW_SELL": False, "TP_RR": 7.0}),
        ("buy_be003", {"ALLOW_SELL": False, "BE_RR": 0.03}),
        ("buy_be005", {"ALLOW_SELL": False, "BE_RR": 0.05}),
        ("buy_be020", {"ALLOW_SELL": False, "BE_RR": 0.20}),
        ("buy_no_be", {"ALLOW_SELL": False, "BE_RR": None}),
        (
            "buy_rr7_no_be",
            {"ALLOW_SELL": False, "TP_RR": 7.0, "BE_RR": None},
        ),
        (
            "buy_recent16",
            {"ALLOW_SELL": False, "TP_RR": 7.0, "RECENT_RETURNS": 16},
        ),
        (
            "buy_recent24",
            {"ALLOW_SELL": False, "TP_RR": 7.0, "RECENT_RETURNS": 24},
        ),
        (
            "buy_loose_tau",
            {
                "ALLOW_SELL": False,
                "TP_RR": 7.0,
                "RECENT_TAU_MIN": 0.12,
                "TAU_JUMP_MIN": 0.10,
            },
        ),
        (
            "buy_strict_tau",
            {
                "ALLOW_SELL": False,
                "TP_RR": 7.0,
                "RECENT_TAU_MIN": 0.20,
                "TAU_JUMP_MIN": 0.18,
            },
        ),
        (
            "buy_wide_session",
            {
                "ALLOW_SELL": False,
                "TP_RR": 7.0,
                "SESSION_START_HOUR": 16,
                "SESSION_END_HOUR": 22,
            },
        ),
    )
    available = dict(probes)
    if args.probe is None:
        print("Available probes:", ", ".join(available))
        return
    if args.probe not in available:
        parser.error(f"unknown probe {args.probe!r}")

    prepared = {
        label: (
            months,
            parse_bkk(end),
            prepare_rates(months, "M5", parse_bkk(end), 300),
        )
        for label, months, end in WINDOWS
    }
    cfg = available[args.probe]
    print(args.probe, cfg, flush=True)
    for label, (months, end, rates) in prepared.items():
        summary, _ = backtest(
            325, months, "M5", 0.20, 0.01, end, 300, cfg, rates
        )
        print(label, _view(summary), flush=True)


if __name__ == "__main__":
    main()
