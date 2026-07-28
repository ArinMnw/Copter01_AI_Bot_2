# -*- coding: utf-8 -*-
"""Cross-window structural-gate and direction sensitivity for S294."""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument(
        "--parameter",
        choices=("f", "slope", "change", "acceleration"),
        required=True,
    )
    parser.add_argument("--values")
    parser.add_argument("--side", choices=("both", "buy", "sell"), default="both")
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    lookback = 300
    prepared = prepare_rates(args.months, "M5", end, lookback)
    fixed = {
        "ALLOW_BUY": args.side in ("both", "buy"),
        "ALLOW_SELL": args.side in ("both", "sell"),
        "CHOW_F_MIN": 2.0,
        "TP_RR": 21.1,
        "BE_RR": 0.525,
    }
    choices = {
        "f": ("CHOW_F_MIN", (2.0, 3.0, 4.0, 5.0, 7.0, 10.0)),
        "slope": ("RECENT_SLOPE_ATR_MIN", (0.015, 0.025, 0.035, 0.050)),
        "change": ("SLOPE_CHANGE_ATR_MIN", (0.010, 0.020, 0.030, 0.050)),
        "acceleration": ("SLOPE_ACCELERATION_MIN", (0.8, 1.1, 1.4, 1.8)),
    }
    key, values = choices[args.parameter]
    if args.values:
        values = tuple(float(value) for value in args.values.split(","))
    for value in values:
        summary, _ = backtest(
            294,
            args.months,
            "M5",
            0.20,
            0.01,
            end,
            lookback,
            cfg={**fixed, key: value},
            prepared=prepared,
        )
        print(
            json.dumps(
                {
                    "parameter": key,
                    "value": value,
                    "side": args.side,
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
