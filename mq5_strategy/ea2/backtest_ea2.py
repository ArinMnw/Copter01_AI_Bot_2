# -*- coding: utf-8 -*-
"""Standalone EA2 backtest; M1 is MQ5 parity, other TFs are research only."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HERE = os.path.dirname(os.path.abspath(__file__))
for _path in (_ROOT, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import config
from ea_strategy_2 import DEFAULT_CFG, run_backtest

BKK = timezone(timedelta(hours=7))
TF_MAP = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
    "H12": mt5.TIMEFRAME_H12, "D1": mt5.TIMEFRAME_D1,
}
TF_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600,
    "H4": 14400, "H12": 43200, "D1": 86400,
}
TF_ORDER = tuple(TF_MAP)


def parse_bkk(value):
    dt = datetime.fromisoformat(value) if value else datetime.now(BKK)
    return dt.replace(tzinfo=BKK) if dt.tzinfo is None else dt.astimezone(BKK)


def fmt_bkk(dt):
    return dt.astimezone(BKK).strftime("%Y-%m-%d %H:%M:%S")


def bar_time_to_bkk(raw_time):
    return datetime.fromtimestamp(int(raw_time), tz=BKK) - timedelta(hours=1)


def bkk_to_query(dt):
    return dt + timedelta(hours=1)


def csv_path_for_tf(path, tf):
    stem, ext = os.path.splitext(path)
    return f"{stem}_{tf}{ext or '.csv'}"


def prepare_rates(tf, start_bkk, end_bkk, cfg):
    lookback = int(cfg["MAX_BARS_LOOKBACK"]) + int(cfg["SWING_BARS"]) * 2 + 20
    history_days = math.ceil(lookback * TF_SECONDS[tf] / 86400 * 7 / 5) + 20
    if not config.mt5_initialize(mt5):
        raise RuntimeError("MT5 initialization failed")
    rates = mt5.copy_rates_range(
        config.SYMBOL, TF_MAP[tf], bkk_to_query(start_bkk - timedelta(days=history_days)),
        bkk_to_query(end_bkk),
    )
    mt5.shutdown()
    if rates is None or len(rates) <= lookback + 20:
        raise RuntimeError(f"not enough MT5 rates ({0 if rates is None else len(rates)})")
    bars = list(rates)
    start_query_ts = int(bkk_to_query(start_bkk).timestamp())
    start_bar = next((i for i, bar in enumerate(bars) if int(bar["time"]) >= start_query_ts), None)
    if start_bar is None or start_bar < lookback:
        raise RuntimeError(f"not enough warm-up bars before start ({start_bar}/{lookback})")
    return bars, start_bar


def monthly_breakdown(trades):
    buckets = defaultdict(lambda: {"net": 0.0, "closed": 0, "wins": 0})
    for trade in trades:
        bucket = buckets[trade["exit_time"][:7]]
        bucket["net"] += trade["profit"]
        bucket["closed"] += 1
        bucket["wins"] += trade["profit"] > 0
    return dict(sorted(buckets.items()))


def backtest_tf(tf, spread, lot, start_bkk, end_bkk, cfg):
    bars, start_bar = prepare_rates(tf, start_bkk, end_bkk, cfg)
    t0 = time.time()
    raw_trades, extra = run_backtest(
        bars, cfg, spread=spread, contract_multiplier=100.0 * lot, start_bar=start_bar
    )
    elapsed = time.time() - t0
    trades = []
    for trade in raw_trades:
        entry_time = bar_time_to_bkk(bars[trade["entry_bar"]]["time"])
        if entry_time < start_bkk or entry_time >= end_bkk:
            continue
        row = {
            "entry_time": fmt_bkk(entry_time),
            "exit_time": fmt_bkk(bar_time_to_bkk(bars[trade["exit_bar"]]["time"])),
            **{k: trade[k] for k in ("direction", "entry", "sl", "tp", "exit_price", "outcome", "profit", "pattern", "reason")},
        }
        trades.append(row)

    profits = [trade["profit"] for trade in trades]
    wins = sum(p > 0 for p in profits)
    gross_win = sum(p for p in profits if p > 0)
    gross_loss = -sum(p for p in profits if p < 0)
    equity = peak = max_dd = 0.0
    for profit in profits:
        equity += profit
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    days = max(1.0, (end_bkk - start_bkk).total_seconds() / 86400)
    return {
        "strategy": "EA2", "tf": tf, "start": fmt_bkk(start_bkk), "end": fmt_bkk(end_bkk),
        "days": round(days, 1), "spread": spread, "lot": lot, "elapsed_sec": round(elapsed, 2),
        "entries": extra["entries"], "closed": len(trades), "wins": wins,
        "win_rate": wins / len(trades) * 100 if trades else None,
        "net_profit": sum(profits), "pnl_per_day": sum(profits) / days,
        "profit_factor": gross_win / gross_loss if gross_loss else (math.inf if gross_win else None),
        "max_drawdown": max_dd, "monthly": monthly_breakdown(trades),
        "signals": {
            key: value for key, value in extra.items()
            if key not in ("entries", "open_positions", "entry_events", "state_snapshot")
        },
    }, trades


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", help="BKK ISO start")
    parser.add_argument("--end", help="BKK ISO end; default now")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--tf", choices=TF_ORDER + ("all",), default="M1",
                        help="M1 matches the source MQ5; other TFs are research-only")
    parser.add_argument("--spread", type=float, default=0.20)
    parser.add_argument("--balance", type=float, default=100.0)
    parser.add_argument("--lot", type=float)
    parser.add_argument("--cfg-json", default="{}")
    parser.add_argument("--csv", default=os.path.join(_HERE, "ea2_trades.csv"))
    parser.add_argument("--summary-json", default=os.path.join(_HERE, "ea2_summary_365d.json"))
    args = parser.parse_args()
    if args.start and args.days != 365:
        parser.error("use --start or --days, not both")
    end_bkk = parse_bkk(args.end)
    start_bkk = parse_bkk(args.start) if args.start else end_bkk - timedelta(days=args.days)
    lot = args.lot if args.lot is not None else args.balance / 10000.0
    cfg = dict(DEFAULT_CFG)
    cfg.update(json.loads(args.cfg_json))
    tf_list = TF_ORDER if args.tf == "all" else (args.tf,)
    results = {}
    print(f"EA2 | {fmt_bkk(start_bkk)} -> {fmt_bkk(end_bkk)} | lot={lot:.2f} spread={args.spread:.2f}")
    for tf in tf_list:
        print(f"\n===== TF={tf} =====")
        try:
            summary, trades = backtest_tf(tf, args.spread, lot, start_bkk, end_bkk, cfg)
        except RuntimeError as exc:
            print(f"SKIP: {exc}")
            continue
        results[tf] = summary
        out_csv = csv_path_for_tf(args.csv, tf)
        fields = ("entry_time", "exit_time", "direction", "entry", "sl", "tp", "exit_price", "outcome", "profit", "pattern", "reason")
        with open(out_csv, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(trades)
        pf = summary["profit_factor"]
        pf_text = "N/A" if pf is None else ("inf" if pf == math.inf else f"{pf:.2f}")
        wr_text = "N/A" if summary["win_rate"] is None else f"{summary['win_rate']:.2f}%"
        print(f"PnL={summary['net_profit']:.2f} | PF={pf_text} | "
              f"WR={wr_text} | W/Trades={summary['wins']}/{summary['closed']} | "
              f"MaxDD={summary['max_drawdown']:.2f} | elapsed={summary['elapsed_sec']:.2f}s")

    print("\n===== EA2 365-DAY SUMMARY =====")
    print(f"{'TF':<6}{'PnL':>12}{'PF':>9}{'WR':>9}{'W/Trades':>13}{'MaxDD':>12}")
    for tf, summary in results.items():
        pf = summary["profit_factor"]
        pf_text = "N/A" if pf is None else ("inf" if pf == math.inf else f"{pf:.2f}")
        wr = "N/A" if summary["win_rate"] is None else f"{summary['win_rate']:.1f}%"
        wins_trades = f"{summary['wins']}/{summary['closed']}"
        print(f"{tf:<6}{summary['net_profit']:>12.2f}{pf_text:>9}{wr:>9}"
              f"{wins_trades:>13}{summary['max_drawdown']:>12.2f}")
    for summary in results.values():
        if summary["profit_factor"] == math.inf:
            summary["profit_factor"] = None
    with open(args.summary_json, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2, allow_nan=False)
    print(f"\nSummary JSON: {args.summary_json}")


if __name__ == "__main__":
    main()
