# -*- coding: utf-8 -*-
"""Cross-window structure sensitivity sweep for optimized S286."""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def _row(label, value, summary):
    return {
        "parameter": label,
        "value": value,
        "signals": summary["signals"],
        "closed": summary["closed"],
        "wins": summary["wins"],
        "win_rate": summary["win_rate"],
        "net": summary["net_profit"],
        "pf": summary["profit_factor"],
        "max_dd": summary["max_drawdown"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument(
        "--parameter",
        choices=("mk", "sweep", "all"),
        default="all",
    )
    parser.add_argument("--values", help="Optional comma-separated integers")
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    lookback = 300
    prepared = prepare_rates(args.months, "M5", end, lookback)
    fixed = {
        "ALLOW_BUY": False,
        "ALLOW_SELL": True,
        "MK_Z_MIN_ABS": 2.50,
        "TP_RR": 27.00,
        "BE_RR": 1.59,
    }
    mk_values = (32, 48, 64, 80, 96, 128)
    sweep_values = (6, 8, 10, 12, 14, 16)
    if args.values:
        selected = tuple(int(value) for value in args.values.split(","))
        if args.parameter == "mk":
            mk_values, sweep_values = selected, ()
        elif args.parameter == "sweep":
            mk_values, sweep_values = (), selected
    cases = [
        ("MK_LOOKBACK", value, {**fixed, "MK_LOOKBACK": value})
        for value in mk_values
        if args.parameter in ("mk", "all")
    ]
    cases += [
        ("SWEEP_LOOKBACK", value, {**fixed, "SWEEP_LOOKBACK": value})
        for value in sweep_values
        if args.parameter in ("sweep", "all")
    ]
    for label, value, cfg in cases:
        summary, _ = backtest(
            286,
            args.months,
            "M5",
            0.20,
            0.01,
            end,
            lookback,
            cfg=cfg,
            prepared=prepared,
        )
        print(json.dumps(_row(label, value, summary), allow_nan=True), flush=True)


if __name__ == "__main__":
    main()
