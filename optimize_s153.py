# -*- coding: utf-8 -*-
"""Bounded payoff sensitivity for S153."""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


CASES = ((7.0, 0.75), (7.0, 1.0), (7.0, 1.25),
         (8.0, 1.0), (10.0, 1.0), (12.0, 1.0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    prepared = prepare_rates(args.months, "M5", end, 300)
    rows = []
    for rr, be in CASES:
        summary, _ = backtest(153, args.months, "M5", 0.20, 0.01, end, 300,
                              cfg={"TP_RR": rr, "BE_RR": be}, prepared=prepared)
        rows.append({"rr": rr, "be": be, "closed": summary["closed"],
                     "wins": summary["wins"], "win_rate": summary["win_rate"],
                     "net": summary["net_profit"], "pf": summary["profit_factor"],
                     "max_dd": summary["max_drawdown"]})
    rows.sort(key=lambda row: (row["net"], -row["max_dd"]), reverse=True)
    for row in rows:
        print(json.dumps(row, allow_nan=True))


if __name__ == "__main__":
    main()
