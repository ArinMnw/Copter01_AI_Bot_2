# -*- coding: utf-8 -*-
"""Cross-window shape and rejection sensitivity for S298."""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--parameter",
        choices=("jb", "skew", "sweep", "wick"),
        required=True,
    )
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--values")
    args = parser.parse_args()
    choices = {
        "jb": ("JARQUE_BERA_MIN", (0.0, 1.0, 2.0, 3.0, 4.0, 6.0)),
        "skew": ("ABS_SKEW_MIN", (0.0, 0.05, 0.10, 0.15, 0.20, 0.25)),
        "sweep": ("SWEEP_LOOKBACK", (10, 12, 14, 16, 18, 20)),
        "wick": (
            "REJECTION_WICK_FRACTION_MIN",
            (0.20, 0.24, 0.28, 0.32, 0.36),
        ),
    }
    key, values = choices[args.parameter]
    if args.values:
        values = tuple(float(value) for value in args.values.split(","))
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    prepared = prepare_rates(args.months, "M5", end, 300)
    fixed = {
        "ALLOW_BUY": False,
        "ALLOW_SELL": True,
        "JARQUE_BERA_MIN": 0.25,
        "ABS_SKEW_MIN": 0.10,
        "SWEEP_LOOKBACK": 14,
        "TP_RR": 24.0,
        "BE_RR": 1.575,
    }
    for value in values:
        summary, _ = backtest(
            298,
            args.months,
            "M5",
            0.20,
            0.01,
            end,
            300,
            cfg={**fixed, key: value},
            prepared=prepared,
        )
        print(
            json.dumps(
                {
                    "parameter": key,
                    "value": value,
                    "signals": summary["signals"],
                    "closed": summary["closed"],
                    "wins": summary["wins"],
                    "win_rate": summary["win_rate"],
                    "net": summary["net_profit"],
                    "pf": summary["profit_factor"],
                    "max_dd": summary["max_drawdown"],
                },
                allow_nan=True,
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
