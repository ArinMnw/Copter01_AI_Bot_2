# -*- coding: utf-8 -*-
"""Cross-window sample-geometry sensitivity for optimized S301."""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--parameter",
        choices=("baseline", "recent", "body", "range", "close"),
        required=True,
    )
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--values")
    args = parser.parse_args()
    choices = {
        "baseline": ("BASELINE_RETURNS", (40, 44, 48, 52, 56)),
        "recent": ("RECENT_RETURNS", (12, 14, 16, 18, 20)),
        "body": ("RELEASE_BODY_ATR_MIN", (0.40, 0.50, 0.55, 0.60, 0.70)),
        "range": ("RELEASE_RANGE_ATR_MIN", (0.55, 0.65, 0.75, 0.85, 0.95)),
        "close": ("RELEASE_CLOSE_FRACTION", (0.55, 0.60, 0.62, 0.65, 0.70)),
    }
    key, values = choices[args.parameter]
    if args.values:
        values = tuple(float(value) for value in args.values.split(","))
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    prepared = prepare_rates(args.months, "M5", end, 300)
    fixed = {
        "ALLOW_BUY": False,
        "ALLOW_SELL": True,
        "KS_SCALED_MIN": 1.05,
        "MEDIAN_SHIFT_MAD_MIN": 0.125,
        "TP_RR": 10.2,
        "BE_RR": 0.25,
    }
    for value in values:
        summary, _ = backtest(
            301,
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
