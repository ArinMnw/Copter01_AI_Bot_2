# -*- coding: utf-8 -*-
"""Cross-window Pettitt threshold sensitivity for optimized S287."""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--parameter", choices=("p", "shift", "age"), required=True)
    parser.add_argument("--values", help="Optional comma-separated numeric values")
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    lookback = 300
    prepared = prepare_rates(args.months, "M5", end, lookback)
    fixed = {
        "ALLOW_BUY": True,
        "ALLOW_SELL": False,
        "PETTITT_P_MAX": 0.025,
        "SHIFT_ATR_MIN": 1.25,
        "TP_RR": 29.8,
        "BE_RR": 0.70,
    }
    if args.parameter == "p":
        cases = [
            ("PETTITT_P_MAX", value, {**fixed, "PETTITT_P_MAX": value})
            for value in (0.01, 0.025, 0.05, 0.10)
        ]
    elif args.parameter == "shift":
        cases = [
            ("SHIFT_ATR_MIN", value, {**fixed, "SHIFT_ATR_MIN": value})
            for value in (1.00, 1.25, 1.50, 2.00)
        ]
    else:
        age_values = (16, 20, 24, 28, 32)
        if args.values:
            age_values = tuple(int(value) for value in args.values.split(","))
        cases = [
            (
                "CHANGE_MAX_AGE",
                value,
                {**fixed, "CHANGE_MIN_AGE": 8, "CHANGE_MAX_AGE": value},
            )
            for value in age_values
        ]
    for label, value, cfg in cases:
        summary, _ = backtest(
            287,
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
                    "parameter": label,
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
