# -*- coding: utf-8 -*-
"""Small, reproducible payoff grid for S135 using one shared MT5 dataset."""

from __future__ import annotations

import argparse
import itertools
import json

from sim_strategy_backtest import BKK, backtest, parse_bkk, prepare_rates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--end", default="2026-07-17T00:00:00+07:00")
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--rr", default="7,8,10,12")
    parser.add_argument("--be", default="0.75,1.0,1.25")
    parser.add_argument("--max-risk-atr", default="",
                        help="Optional comma-separated S120 MAX_RISK_ATR grid")
    parser.add_argument("--rv-min", default="",
                        help="Optional comma-separated S120 RV_EXPANSION_MIN grid")
    parser.add_argument("--previous-rv-max", default="",
                        help="Optional comma-separated S120 PREVIOUS_RV_MAX grid")
    args = parser.parse_args()
    end = parse_bkk(args.end).astimezone(BKK)
    rr_values = [float(value) for value in args.rr.split(",")]
    be_values = [float(value) for value in args.be.split(",")]
    risk_values = ([float(value) for value in args.max_risk_atr.split(",")]
                   if args.max_risk_atr else [None])
    rv_values = ([float(value) for value in args.rv_min.split(",")]
                 if args.rv_min else [None])
    previous_values = ([float(value) for value in args.previous_rv_max.split(",")]
                       if args.previous_rv_max else [None])
    prepared = prepare_rates(args.months, "M5", end, 300)
    rows = []
    grid = itertools.product(rr_values, be_values, risk_values, rv_values, previous_values)
    for rr, be, max_risk, rv_min, previous_max in grid:
        cfg = {"TP_RR": rr, "BE_RR": be}
        source = {}
        if max_risk is not None:
            source["MAX_RISK_ATR"] = max_risk
        if rv_min is not None:
            source["RV_EXPANSION_MIN"] = rv_min
        if previous_max is not None:
            source["PREVIOUS_RV_MAX"] = previous_max
        if source:
            cfg["SOURCE_CFG"] = {"S120_CFG": source}
        summary, _ = backtest(135, args.months, "M5", 0.20, 0.01, end, 300,
                              cfg=cfg, prepared=prepared)
        rows.append({
            "rr": rr, "be": be, "max_risk_atr": max_risk,
            "rv_min": rv_min, "previous_rv_max": previous_max,
            "closed": summary["closed"],
            "wins": summary["wins"], "win_rate": summary["win_rate"],
            "net": summary["net_profit"], "pf": summary["profit_factor"],
            "max_dd": summary["max_drawdown"],
        })
    rows.sort(key=lambda row: (row["net"], -row["max_dd"]), reverse=True)
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, allow_nan=True))


if __name__ == "__main__":
    main()
