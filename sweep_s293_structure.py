# -*- coding: utf-8 -*-
"""Cross-window regime and sweep-geometry sensitivity for S293."""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--parameter", choices=("z", "rho", "sweep"), required=True)
    parser.add_argument("--values")
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    lookback = 300
    prepared = prepare_rates(args.months, "M5", end, lookback)
    fixed = {"TP_RR": 25.1, "BE_RR": 0.875}
    if args.parameter == "z":
        key = "LJUNG_BOX_Z_MIN"
        values = (0.00, 0.25, 0.50, 0.75, 1.00)
    elif args.parameter == "rho":
        key = "WEIGHTED_AUTOCORR_MAX"
        values = (-0.05, -0.03, -0.015, 0.00, 0.015)
    else:
        key = "SWEEP_LOOKBACK"
        values = (8, 10, 12, 14, 16)
    if args.values:
        values = tuple(float(value) for value in args.values.split(","))
    for value in values:
        summary, _ = backtest(
            293,
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
