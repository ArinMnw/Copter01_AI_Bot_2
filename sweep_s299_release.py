# -*- coding: utf-8 -*-
"""Cross-window directional-release sensitivity for S299."""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--parameter",
        choices=("direction", "displacement", "body"),
        required=True,
    )
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--values")
    args = parser.parse_args()
    choices = {
        "direction": ("DIRECTION_WINDOW", (8, 10, 12, 14, 16)),
        "displacement": (
            "DIRECTION_DISPLACEMENT_ATR_MIN",
            (0.25, 0.35, 0.45, 0.55, 0.65),
        ),
        "body": ("RELEASE_BODY_ATR_MIN", (0.40, 0.50, 0.55, 0.60, 0.70)),
    }
    key, values = choices[args.parameter]
    if args.values:
        values = tuple(float(value) for value in args.values.split(","))
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    prepared = prepare_rates(args.months, "M5", end, 300)
    fixed = {
        "ALLOW_BUY": False,
        "ALLOW_SELL": True,
        "GINI_MIN": 0.47,
        "TOP_QUARTILE_SHARE_MIN": 0.57,
        "TP_RR": 52.5,
        "BE_RR": 0.25,
    }
    for value in values:
        summary, _ = backtest(
            299,
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
