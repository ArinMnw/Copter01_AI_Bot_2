# -*- coding: utf-8 -*-
"""Evaluate many S199 cfg overrides on one shared MT5 price fetch.

Example:
    python optimize_s199_multi.py --months 6 --cases '[{"BE_RR": 0.65}, {"BE_RR": 0.85}]'
"""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", type=int, default=199)
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--cases", required=True,
                        help="JSON list of cfg override objects")
    parser.add_argument("--end", default="2026-07-18T00:00:00+07:00")
    parser.add_argument("--spread", type=float, default=0.20)
    parser.add_argument("--lookback", type=int, default=300)
    args = parser.parse_args()
    cases = json.loads(args.cases)
    if not isinstance(cases, list) or not all(isinstance(c, dict) for c in cases):
        parser.error("--cases must be a JSON list of objects")
    end = parse_bkk(args.end)
    lookback = args.lookback
    prepared = prepare_rates(args.months, "M5", end, lookback)
    for case in cases:
        summary, _ = backtest(args.strategy, args.months, "M5", args.spread, 0.01,
                              end, lookback, cfg=case, prepared=prepared)
        print(json.dumps({
            "cfg": case, "closed": summary["closed"],
            "win_rate": round(summary["win_rate"], 2) if summary["win_rate"] else summary["win_rate"],
            "net": round(summary["net_profit"], 2),
            "pnl_day": round(summary["pnl_per_day"], 2),
            "pnl_month": round(summary["pnl_per_month"], 2),
            "pf": round(summary["profit_factor"], 2) if summary["profit_factor"] else summary["profit_factor"],
            "max_dd": round(summary["max_drawdown"], 2),
        }), flush=True)


if __name__ == "__main__":
    main()
