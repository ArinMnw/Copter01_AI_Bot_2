# -*- coding: utf-8 -*-
"""Map which BKK hours carry a tradeable drive edge, on one shared price fetch.

Runs the S206 drive skeleton over every hour-of-day window so the hour is the
only variable, across two half-year windows. Purpose: stop guessing sessions one
at a time (S219's PM-fix guess cost a full cycle) and instead see the whole
edge-by-hour map at once.

Example:
    python scan_session_hours.py --tf M15 --range-bars 3
"""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", type=int, default=206)
    parser.add_argument("--tf", default="M15")
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--range-bars", type=int, default=3)
    parser.add_argument("--lookback", type=int, default=300)
    parser.add_argument("--ends", default="2026-07-18,2026-01-18",
                        help="comma-separated BKK end dates (one per window)")
    parser.add_argument("--width", type=int, default=2,
                        help="session width in hours")
    args = parser.parse_args()

    windows = []
    for end_date in args.ends.split(","):
        end = parse_bkk(end_date.strip() + "T00:00:00+07:00")
        prepared = prepare_rates(args.months, args.tf, end, args.lookback)
        windows.append((end_date.strip(), end, prepared))

    rows = []
    for hour in range(24):
        cfg = {
            "RANGE_BARS": args.range_bars,
            "SESSION_START_HOUR": hour,
            "SESSION_END_HOUR": (hour + args.width) % 24 or 24,
        }
        if hour + args.width > 24:
            continue  # skip wrap-around windows
        row = {"hour": f"{hour:02d}-{hour + args.width:02d}"}
        total = 0.0
        ok = True
        for label, end, prepared in windows:
            summary, _ = backtest(args.strategy, args.months, args.tf, 0.20, 0.01,
                                  end, args.lookback, cfg=cfg, prepared=prepared)
            net = round(summary["net_profit"], 2)
            row[label] = {
                "n": summary["closed"],
                "net": net,
                "pf": round(summary["profit_factor"], 2) if summary["profit_factor"] else None,
                "dd": round(summary["max_drawdown"], 2),
            }
            total += net
            if net <= 0:
                ok = False
        row["total"] = round(total, 2)
        row["both_positive"] = ok
        rows.append(row)
        print(json.dumps(row), flush=True)

    print("\n=== hours positive in BOTH windows ===", flush=True)
    for row in sorted((r for r in rows if r["both_positive"]),
                      key=lambda r: r["total"], reverse=True):
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
