# -*- coding: utf-8 -*-
"""Six-month payoff validation for S158 confirmation acceptance."""

from __future__ import annotations

import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def main():
    months = 6
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    prepared = prepare_rates(months, "M5", end, 300)
    for rr in (7.0, 8.0, 10.0, 12.0):
        cfg = {"CONFIRM_CLOSE_FRACTION": 0.80, "TP_RR": rr, "BE_RR": 1.0}
        summary, _ = backtest(158, months, "M5", 0.20, 0.01, end, 300,
                              cfg=cfg, prepared=prepared)
        print(json.dumps({
            "rr": rr,
            "closed": summary["closed"],
            "wins": summary["wins"],
            "win_rate": summary["win_rate"],
            "net": summary["net_profit"],
            "pf": summary["profit_factor"],
            "max_dd": summary["max_drawdown"],
        }, allow_nan=True), flush=True)


if __name__ == "__main__":
    main()
