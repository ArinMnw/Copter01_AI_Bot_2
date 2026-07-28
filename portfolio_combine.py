# -*- coding: utf-8 -*-
"""Combine saved per-strategy trades into one portfolio equity curve per window."""
import json
import math
import os
from datetime import datetime

DAY_WINDOWS = [30, 60, 90, 120, 150, 365]
COMBINE_STRATS = [206, 258, 294, 172, 165, 166, 104, 105, 106]
TRADES_DIR = "portfolio_backtest_trades"


def load_trades(sid, days):
    path = os.path.join(TRADES_DIR, f"s{sid}_{days}d.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_dt(s):
    return datetime.fromisoformat(s)


def combined_stats(all_trades):
    all_trades.sort(key=lambda t: parse_dt(t["exit_time"]))
    profits = [t["profit"] for t in all_trades]
    wins = sum(p > 0 for p in profits)
    gross_win = sum(p for p in profits if p > 0)
    gross_loss = -sum(p for p in profits if p < 0)
    net = sum(profits)
    equity = peak = max_dd = 0.0
    for p in profits:
        equity += p
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    pf = (gross_win / gross_loss) if gross_loss else (math.inf if gross_win else None)
    return {
        "closed": len(all_trades), "wins": wins,
        "win_rate": (wins / len(all_trades) * 100.0) if all_trades else None,
        "net": net, "pf": pf, "max_dd": max_dd,
    }


def main():
    print(f"{'Days':>5} {'Closed':>7} {'Wins':>6} {'Net':>12} {'PF':>10} {'MaxDD':>10}")
    rows = []
    for days in DAY_WINDOWS:
        all_trades = []
        for sid in COMBINE_STRATS:
            all_trades.extend(load_trades(sid, days))
        stats = combined_stats(all_trades)
        pf_str = f"{stats['pf']:.2f}" if isinstance(stats['pf'], float) and math.isfinite(stats['pf']) else str(stats['pf'])
        print(f"{days:>5} {stats['closed']:>7} {stats['wins']:>6} {stats['net']:>12.2f} {pf_str:>10} {stats['max_dd']:>10.2f}")
        rows.append((days, stats))

    with open("portfolio_combined_results_v2.json", "w", encoding="utf-8") as f:
        json.dump([{"days": d, **s} for d, s in rows], f, indent=2, default=str)


if __name__ == "__main__":
    main()
