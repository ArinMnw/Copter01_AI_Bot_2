# -*- coding: utf-8 -*-
"""Bounded payoff sensitivity for marginal S151."""

from __future__ import annotations

import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


CASES = ((7.0, 0.75), (7.0, 1.0), (7.0, 1.25),
         (8.0, 1.0), (10.0, 1.0), (12.0, 1.0))


def main():
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    prepared = prepare_rates(2, "M5", end, 300)
    rows = []
    for rr, be in CASES:
        cfg = {"TP_RR": rr, "BE_RR": be}
        summary, _ = backtest(151, 2, "M5", 0.20, 0.01, end, 300,
                              cfg=cfg, prepared=prepared)
        rows.append({"rr": rr, "be": be, "closed": summary["closed"],
                     "wins": summary["wins"], "net": summary["net_profit"],
                     "pf": summary["profit_factor"], "max_dd": summary["max_drawdown"]})
    rows.sort(key=lambda row: (row["net"], -row["max_dd"]), reverse=True)
    for row in rows:
        print(json.dumps(row, allow_nan=True))


if __name__ == "__main__":
    main()
