# -*- coding: utf-8 -*-
"""Cross-window structural and rejection sensitivity for S296."""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument(
        "--parameter",
        choices=("f", "sweep", "wick", "reclaim"),
        required=True,
    )
    parser.add_argument("--values")
    args = parser.parse_args()
    choices = {
        "f": ("SUP_CHOW_F_MIN", (5.0, 7.5, 10.0, 12.5, 15.0, 20.0)),
        "sweep": ("SWEEP_LOOKBACK", (10, 12, 14, 16, 18, 20)),
        "wick": (
            "REJECTION_WICK_FRACTION_MIN",
            (0.20, 0.24, 0.28, 0.32, 0.36),
        ),
        "reclaim": ("RECLAIM_MIN_ATR", (0.00, 0.01, 0.02, 0.03, 0.04)),
    }
    key, values = choices[args.parameter]
    if args.values:
        values = tuple(float(value) for value in args.values.split(","))
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    prepared = prepare_rates(args.months, "M5", end, 300)
    fixed = {
        "ALLOW_BUY": False,
        "ALLOW_SELL": True,
        "TP_RR": 26.8,
        "BE_RR": 0.3125,
    }
    for value in values:
        summary, _ = backtest(
            296,
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
