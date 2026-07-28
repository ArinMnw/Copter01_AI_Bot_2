# -*- coding: utf-8 -*-
"""Cross-window distribution-drift sensitivity for S290."""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--parameter", choices=("w1", "shift"), required=True)
    parser.add_argument("--values")
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    lookback = 300
    prepared = prepare_rates(args.months, "M5", end, lookback)
    if args.parameter == "w1":
        key = "WASSERSTEIN_MAD_MIN"
        values = (0.50, 0.75, 1.00, 1.25, 1.50)
    else:
        key = "MEDIAN_SHIFT_MAD_MIN"
        values = (0.700, 0.725, 0.750, 0.775, 0.800, 0.825, 0.850)
    if args.values:
        values = tuple(float(value) for value in args.values.split(","))
    for value in values:
        summary, _ = backtest(
            290,
            args.months,
            "M5",
            0.20,
            0.01,
            end,
            lookback,
            cfg={key: value},
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
