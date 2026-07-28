# -*- coding: utf-8 -*-
"""Cross-window Mood scale-regime sensitivity for optimized S288."""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument(
        "--parameter",
        choices=("z", "window", "displacement"),
        required=True,
    )
    parser.add_argument("--values", help="Optional comma-separated numeric values")
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    lookback = 300
    prepared = prepare_rates(args.months, "M5", end, lookback)
    fixed = {"TP_RR": 38.3, "BE_RR": 0.20}
    if args.parameter == "z":
        values = (1.50, 1.75, 2.00, 2.25, 2.50)
        if args.values:
            values = tuple(float(value) for value in args.values.split(","))
        cases = [
            ("MOOD_Z_MIN", value, {**fixed, "MOOD_Z_MIN": value})
            for value in values
        ]
    elif args.parameter == "window":
        window_values = (
            (40, 16),
            (48, 12),
            (48, 16),
            (48, 20),
            (56, 16),
        )
        if args.values:
            window_values = tuple(
                tuple(int(part) for part in value.split("/"))
                for value in args.values.split(",")
            )
        cases = [
            (
                "MOOD_WINDOWS",
                f"{baseline}/{recent}",
                {
                    **fixed,
                    "MOOD_BASELINE_WINDOW": baseline,
                    "MOOD_RECENT_WINDOW": recent,
                },
            )
            for baseline, recent in window_values
        ]
    else:
        cases = [
            (
                "DISPLACEMENT_ATR_MIN",
                value,
                {**fixed, "DISPLACEMENT_ATR_MIN": value},
            )
            for value in (1.00, 1.25, 1.50, 2.00)
        ]
    for label, value, cfg in cases:
        summary, _ = backtest(
            288,
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
