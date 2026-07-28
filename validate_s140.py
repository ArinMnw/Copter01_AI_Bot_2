# -*- coding: utf-8 -*-
"""Walk-forward RR matrix for S140 optimization."""

from __future__ import annotations

import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOW_ENDS = (
    "2026-03-18T00:00:00+07:00",
    "2026-05-18T00:00:00+07:00",
    "2026-07-18T00:00:00+07:00",
)
RR_VALUES = (7.0, 14.0, 20.0, 24.0)


def main():
    for end_text in WINDOW_ENDS:
        end = parse_bkk(end_text)
        prepared = prepare_rates(2, "M5", end, 300)
        for rr in RR_VALUES:
            summary, _ = backtest(
                140, 2, "M5", 0.20, 0.01, end, 300,
                cfg={"TP_RR": rr, "BE_RR": 1.0}, prepared=prepared,
            )
            print(json.dumps({
                "window_end": end_text[:10], "rr": rr,
                "signals": summary["signals"], "closed": summary["closed"],
                "wins": summary["wins"], "win_rate": summary["win_rate"],
                "net": summary["net_profit"], "pf": summary["profit_factor"],
                "max_dd": summary["max_drawdown"],
            }, allow_nan=True), flush=True)


if __name__ == "__main__":
    main()
