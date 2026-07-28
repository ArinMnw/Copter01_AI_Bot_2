# -*- coding: utf-8 -*-
"""Cross-window distribution-shape sensitivity for S297."""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--parameter",
        choices=("jb", "skew", "lookback"),
        required=True,
    )
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--values")
    args = parser.parse_args()
    choices = {
        "jb": ("JARQUE_BERA_MIN", (0.0, 3.0, 6.0, 9.0, 12.0, 20.0)),
        "skew": ("ABS_SKEW_MIN", (0.10, 0.20, 0.25, 0.30, 0.40, 0.50)),
        "lookback": ("RETURN_LOOKBACK", (48, 56, 64, 72, 80)),
    }
    key, values = choices[args.parameter]
    if args.values:
        values = tuple(float(value) for value in args.values.split(","))
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    prepared = prepare_rates(args.months, "M5", end, 300)
    fixed = {
        "ALLOW_BUY": False,
        "ALLOW_SELL": True,
        "JARQUE_BERA_MIN": 28.0,
        "ABS_SKEW_MIN": 0.40,
        "TP_RR": 52.5,
        "BE_RR": 0.2875,
    }
    for value in values:
        summary, _ = backtest(
            297,
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
