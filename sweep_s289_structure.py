# -*- coding: utf-8 -*-
"""Cross-window contraction and release sensitivity for optimized S289."""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument(
        "--parameter",
        choices=("z", "body"),
        required=True,
    )
    parser.add_argument("--values", help="Optional comma-separated numeric values")
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    lookback = 300
    prepared = prepare_rates(args.months, "M5", end, lookback)
    fixed = {"TP_RR": 14.8, "BE_RR": 1.825}
    if args.parameter == "z":
        values = (-1.00, -1.25, -1.50, -1.75, -2.00, -2.25)
        key = "MOOD_Z_MAX"
        fixed["RELEASE_BODY_ATR_MIN"] = 0.925
    else:
        values = (0.40, 0.50, 0.60, 0.70, 0.80, 1.00)
        key = "RELEASE_BODY_ATR_MIN"
        fixed["MOOD_Z_MAX"] = -1.00
    if args.values:
        values = tuple(float(value) for value in args.values.split(","))
    for value in values:
        cfg = {**fixed, key: value}
        summary, _ = backtest(
            289,
            args.months,
            "M5",
            0.20,
            0.01,
            end,
            lookback,
            cfg=cfg,
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
