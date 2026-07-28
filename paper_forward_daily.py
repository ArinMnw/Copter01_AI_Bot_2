# -*- coding: utf-8 -*-
"""Daily paper-forward report for the champion strategies (S206, S202).

Example:
    python paper_forward_daily.py --since 2026-07-20
"""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", required=True,
                        help="BKK date (YYYY-MM-DD); report trades signalled on/after it")
    parser.add_argument("--strategies", default="206,202")
    parser.add_argument("--months", type=int, default=1,
                        help="history window used to warm up and simulate")
    args = parser.parse_args()
    since = parse_bkk(args.since + "T00:00:00+07:00")
    end = parse_bkk(None)
    for strategy_id in (int(s) for s in args.strategies.split(",")):
        summary, trades = backtest(strategy_id, args.months, "M5", 0.20, 0.01,
                                   end, 320)
        recent = [t for t in trades
                  if parse_bkk(t["signal_time"]) >= since]
        net = sum(t["profit"] for t in recent)
        wins = sum(t["profit"] > 0.0 for t in recent)
        print(json.dumps({
            "strategy": f"S{strategy_id}",
            "since": args.since,
            "end": end.isoformat(),
            "trades": len(recent),
            "wins": wins,
            "net": round(net, 2),
        }))
        for t in recent:
            print(f"  {t['signal_time']} {t['direction']} entry={t['entry']} "
                  f"sl={t['sl']} tp={t['tp']} -> {t['outcome']} {t['profit']:+.2f}")


if __name__ == "__main__":
    main()
