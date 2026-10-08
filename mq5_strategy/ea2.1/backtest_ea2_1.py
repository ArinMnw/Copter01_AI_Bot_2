# -*- coding: utf-8 -*-
"""Standalone 365-day all-timeframe backtest for EA2.1."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from datetime import timedelta
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EA2_DIR = HERE.parent / "ea2"
for path in (ROOT, EA2_DIR, HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtest_ea2 import (  # noqa: E402
    TF_ORDER, TF_SECONDS, bar_time_to_bkk, bkk_to_query, csv_path_for_tf,
    fmt_bkk, monthly_breakdown, parse_bkk, prepare_rates,
)
from ea_strategy_2_1 import DEFAULT_CFG, run_backtest_ea2_1  # noqa: E402


HTF_MAP = {
    "M1": "M5", "M5": "M15", "M15": "H1", "M30": "H4",
    "H1": "H4", "H4": "D1", "H12": "D1", "D1": "D1",
}


def metrics(tf, trades, extra, start, end, spread, lot, elapsed):
    profits = [float(trade["profit"]) for trade in trades]
    wins = sum(p > 0 for p in profits)
    gross_win = sum(p for p in profits if p > 0)
    gross_loss = -sum(p for p in profits if p < 0)
    equity = peak = max_dd = 0.0
    for pnl in profits:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        "strategy": "EA2.1", "tf": tf, "htf": HTF_MAP[tf],
        "start": fmt_bkk(start), "end": fmt_bkk(end), "spread": spread, "lot": lot,
        "entries": extra["entries"], "closed": len(trades), "wins": wins,
        "win_rate": wins / len(trades) * 100 if trades else None,
        "net_profit": sum(profits),
        "profit_factor": gross_win / gross_loss if gross_loss else (math.inf if gross_win else None),
        "max_drawdown": max_dd, "elapsed_sec": round(elapsed, 3),
        "monthly": monthly_breakdown(trades),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--start", default="")
    parser.add_argument("--end", default="2026-10-06T21:57:03+07:00")
    parser.add_argument("--tf", choices=TF_ORDER + ("all",), default="all")
    parser.add_argument("--spread", type=float, default=0.20)
    parser.add_argument("--lot", type=float, default=0.01)
    parser.add_argument("--cfg-json", default="{}")
    parser.add_argument("--csv", default=str(HERE / "ea2_1_trades.csv"))
    parser.add_argument("--summary-json", default=str(HERE / "ea2_1_summary_365d.json"))
    args = parser.parse_args()
    end = parse_bkk(args.end)
    start = parse_bkk(args.start) if args.start else end - timedelta(days=args.days)
    cfg = dict(DEFAULT_CFG)
    cfg.update(json.loads(args.cfg_json))
    start_ts = int(bkk_to_query(start).timestamp())
    end_ts = int(bkk_to_query(end).timestamp())
    tf_list = TF_ORDER if args.tf == "all" else (args.tf,)
    results = {}
    print(f"EA2.1 | {fmt_bkk(start)} -> {fmt_bkk(end)} | spread={args.spread:.2f}", flush=True)
    for tf in tf_list:
        htf = HTF_MAP[tf]
        bars, start_bar = prepare_rates(tf, start, end, cfg)
        htf_bars, _ = prepare_rates(htf, start, end, cfg)
        tf_cfg = dict(cfg)
        tf_cfg["TIMEFRAME_SECONDS"] = TF_SECONDS[tf]
        t0 = time.time()
        raw, extra = run_backtest_ea2_1(
            bars, htf_bars, tf_cfg, spread=args.spread,
            contract_multiplier=100.0 * args.lot, start_bar=start_bar,
            timeframe_seconds=TF_SECONDS[tf],
        )
        selected = [
            trade for trade in raw
            if start_ts <= int(bars[trade["entry_bar"]]["time"]) < end_ts
        ]
        rows = []
        for trade in selected:
            rows.append({
                "entry_time": fmt_bkk(bar_time_to_bkk(bars[trade["entry_bar"]]["time"])),
                "exit_time": fmt_bkk(bar_time_to_bkk(bars[trade["exit_bar"]]["time"])),
                **{key: trade[key] for key in (
                    "direction", "entry", "sl", "tp", "exit_price",
                    "outcome", "profit", "pattern", "reason",
                )},
            })
        result = metrics(tf, rows, extra, start, end, args.spread, args.lot, time.time() - t0)
        results[tf] = result
        out_csv = csv_path_for_tf(args.csv, tf)
        with open(out_csv, "w", newline="", encoding="utf-8") as handle:
            fields = (
                "entry_time", "exit_time", "direction", "entry", "sl", "tp",
                "exit_price", "outcome", "profit", "pattern", "reason",
            )
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        pf = result["profit_factor"]
        print(
            f"{tf}/{htf}: PnL={result['net_profit']:.2f} "
            f"PF={'N/A' if pf is None else f'{pf:.2f}'} "
            f"DD={result['max_drawdown']:.2f} trades={result['closed']}",
            flush=True,
        )
    for result in results.values():
        if result["profit_factor"] == math.inf:
            result["profit_factor"] = None
    Path(args.summary_json).write_text(
        json.dumps(results, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8", newline="\n",
    )
    print(f"Summary JSON: {args.summary_json}", flush=True)


if __name__ == "__main__":
    main()
