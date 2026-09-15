# -*- coding: utf-8 -*-
"""Standalone backtest runner สำหรับ S434 Breakout Probability (Expo)
โดยเฉพาะ — โครง prepare_rates()/CLI เหมือน backtest_s433.py เพิ่มสรุป PnL
รายเดือนแยกตาม TF

Usage:
    python backtest_s434.py --days 365 --tf all
    python backtest_s434.py --days 365 --tf M15
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time as _time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config
from strategy434 import DEFAULT_CFG, cfg_for_tf, run_backtest

BKK = timezone(timedelta(hours=7))
TF_MAP = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
    "H12": mt5.TIMEFRAME_H12, "D1": mt5.TIMEFRAME_D1,
}
TF_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400,
    "H12": 43200, "D1": 86400,
}
TF_ORDER = ("M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1")

DEFAULT_DAYS = 30


def parse_bkk(value):
    parsed = datetime.fromisoformat(value) if value else datetime.now(BKK)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BKK)
    return parsed.astimezone(BKK)


def fmt_bkk(dt):
    return dt.astimezone(BKK).strftime("%Y-%m-%d %H:%M:%S")


def _csv_path_for_tf(csv_path, tf_name):
    if "." in csv_path:
        stem, ext = csv_path.rsplit(".", 1)
        return f"{stem}_{tf_name}.{ext}"
    return f"{csv_path}_{tf_name}"


def bar_time_to_bkk(raw_time):
    return datetime.fromtimestamp(int(raw_time), tz=BKK) - timedelta(hours=1)


def bkk_to_query(dt_bkk):
    return dt_bkk + timedelta(hours=1)


def _lookback_bars(cfg):
    min_samples = int(cfg["MIN_SAMPLES"])
    atr_len = int(cfg["ATR_LEN"])
    warmup = max(min_samples, 2)
    return warmup + atr_len + 300


def prepare_rates(tf_name, start_bkk, end_bkk, lookback_bars):
    # ตลาดปิดเสาร์-อาทิตย์ (~5/7 ของปฏิทินเท่านั้นที่มีแท่งจริง) ผลกระทบยิ่งชัดที่
    # TF สูง (H4/H12/D1) เพราะ lookback_bars แท่งต้องใช้ calendar days มากกว่า
    # เดา -> คูณ 7/5 ชดเชยก่อนบวก buffer
    history_days = math.ceil(lookback_bars * TF_SECONDS[tf_name] / 86400.0 * 7.0 / 5.0) + 30
    fetch_start = bkk_to_query(start_bkk - timedelta(days=history_days))
    fetch_end = bkk_to_query(end_bkk)
    if not config.mt5_initialize(mt5):
        raise RuntimeError("MT5 initialization failed")
    rates = mt5.copy_rates_range(config.SYMBOL, TF_MAP[tf_name], fetch_start, fetch_end)
    mt5.shutdown()
    min_bars = lookback_bars + 20
    if rates is None or len(rates) <= min_bars:
        raise RuntimeError("not enough MT5 rates")
    bars = list(rates)
    start_query = bkk_to_query(start_bkk)
    start_index = next(
        (index for index, bar in enumerate(bars)
         if int(bar["time"]) >= int(start_query.timestamp())),
        None,
    )
    if start_index is None or start_index < min_bars:
        raise RuntimeError(
            f"ประวัติ {tf_name} ก่อน --start มีแค่ {start_index} แท่ง ต่ำกว่าขั้นต่ำที่ต้องการ "
            f"({min_bars} แท่ง)"
        )
    return bars


def _monthly_breakdown(trades):
    """สรุป net PnL / จำนวนไม้ / winrate รายเดือน (key = YYYY-MM ตาม exit_time BKK)"""
    buckets = defaultdict(lambda: {"net": 0.0, "closed": 0, "wins": 0})
    for tr in trades:
        month_key = tr["exit_time"][:7]
        b = buckets[month_key]
        b["net"] += tr["profit"]
        b["closed"] += 1
        if tr["profit"] > 0:
            b["wins"] += 1
    return dict(sorted(buckets.items()))


def backtest_tf(tf_name, spread, lot, start_bkk, end_bkk, cfg=None):
    strat_cfg = cfg_for_tf(tf_name, cfg)
    lookback_bars = _lookback_bars(strat_cfg)
    bars_raw = prepare_rates(tf_name, start_bkk, end_bkk, lookback_bars)

    t0 = _time.time()
    contract_multiplier = 100.0 * lot
    raw_trades, extra = run_backtest(bars_raw, strat_cfg, spread=spread,
                                      contract_multiplier=contract_multiplier)
    elapsed = _time.time() - t0

    bars = bars_raw
    trades = []
    for t in raw_trades:
        entry_bar, exit_bar = t["entry_bar"], t["exit_bar"]
        entry_time = bar_time_to_bkk(int(bars[entry_bar]["time"]))
        if entry_time < start_bkk:
            continue
        trades.append({
            "entry_time": fmt_bkk(entry_time),
            "exit_time": fmt_bkk(bar_time_to_bkk(int(bars[exit_bar]["time"]))),
            "direction": t["direction"], "entry": t["entry"], "sl": t["sl"], "tp": t["tp"],
            "exit_price": t["exit_price"], "outcome": t["outcome"], "profit": t["profit"],
            "pattern": t["pattern"], "reason": t["reason"],
        })

    profits = [tr["profit"] for tr in trades]
    wins = sum(p > 0.0 for p in profits)
    gross_win = sum(p for p in profits if p > 0.0)
    gross_loss = -sum(p for p in profits if p < 0.0)
    net = sum(profits)
    equity = peak = max_drawdown = 0.0
    for p in profits:
        equity += p
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    calendar_days = max(1.0, (end_bkk - start_bkk).total_seconds() / 86400.0)
    summary = {
        "strategy": "S434", "tf": tf_name,
        "start": fmt_bkk(start_bkk), "end": fmt_bkk(end_bkk),
        "days": round(calendar_days, 1), "spread": spread, "lot": lot,
        "elapsed_sec": round(elapsed, 1),
        "entries": extra.get("entries"),
        "closed": len(trades), "wins": wins,
        "win_rate": wins / len(trades) * 100.0 if trades else None,
        "net_profit": net,
        "pnl_per_day": net / calendar_days,
        "profit_factor": gross_win / gross_loss if gross_loss else (math.inf if gross_win else None),
        "max_drawdown": max_drawdown,
        "monthly": _monthly_breakdown(trades),
    }
    return summary, trades


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", help="BKK ISO datetime เริ่ม backtest")
    parser.add_argument("--end", help="BKK ISO datetime สิ้นสุด backtest; default = ตอนนี้")
    parser.add_argument("--days", type=int, help="จำนวนวันย้อนหลังจาก --end")
    parser.add_argument("--tf", choices=tuple(TF_MAP) + ("all",), default="M15")
    parser.add_argument("--spread", type=float, default=0.20)
    parser.add_argument("--balance", type=float, default=100.0)
    parser.add_argument("--lot", type=float, default=None)
    parser.add_argument("--cfg-json", default="{}")
    parser.add_argument("--csv", default=os.path.join(_HERE, "s434_trades.csv"))
    parser.add_argument("--summary-json", default=None, help="path เขียนสรุป JSON ทุก TF (สำหรับรายงานต่อ)")
    args = parser.parse_args()

    if args.start and args.days:
        parser.error("ใส่ได้แค่ --start หรือ --days อย่างใดอย่างหนึ่ง ไม่ใช่ทั้งคู่")

    lot = args.lot if args.lot is not None else args.balance / 10000.0
    print(f"lot={lot:.2f}")

    end_bkk = parse_bkk(args.end)
    if args.start:
        start_bkk = parse_bkk(args.start)
    elif args.days:
        start_bkk = end_bkk - timedelta(days=args.days)
    else:
        start_bkk = end_bkk - timedelta(days=DEFAULT_DAYS)
    if start_bkk >= end_bkk:
        parser.error("--start ต้องมาก่อน --end")

    try:
        strat_cfg = json.loads(args.cfg_json)
        if not isinstance(strat_cfg, dict):
            raise ValueError("cfg must be a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        parser.error(f"invalid --cfg-json: {exc}")

    tf_list = TF_ORDER if args.tf == "all" else (args.tf,)
    results = []
    for tf_name in tf_list:
        print(f"\n===== TF={tf_name} =====")
        try:
            summary, trades = backtest_tf(tf_name, args.spread, lot, start_bkk, end_bkk, strat_cfg)
        except RuntimeError as exc:
            print(f"ข้าม TF={tf_name}: {exc}")
            continue
        print({k: v for k, v in summary.items() if k != "monthly"})
        csv_path = _csv_path_for_tf(args.csv, tf_name)
        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=(trades[0].keys() if trades else (
                "entry_time", "exit_time", "direction", "entry", "sl", "tp",
                "exit_price", "outcome", "profit", "pattern", "reason",
            )))
            writer.writeheader()
            writer.writerows(trades)
        print(f"เขียน {len(trades)} ไม้ลง {csv_path}")
        win_rate_str = f"{summary['win_rate']:.2f}%" if summary["win_rate"] is not None else "N/A"
        print("-" * 40)
        print(f"P&L        : {summary['net_profit']:.2f} USD")
        print(f"Win Rate   : {win_rate_str}")
        print(f"Win/Order  : {summary['wins']}/{summary['closed']}")
        print(f"Entries    : {summary['entries']}")
        print("-" * 40)
        print("รายเดือน:")
        for month, m in summary["monthly"].items():
            wr = f"{m['wins'] / m['closed'] * 100:.1f}%" if m["closed"] else "N/A"
            print(f"  {month}: net={m['net']:>10.2f}  closed={m['closed']:>4}  winrate={wr}")
        print("-" * 40)
        results.append((tf_name, summary))

    if len(tf_list) > 1:
        print("\n===== สรุปเทียบทุก TF =====")
        header = f"{'TF':<6}{'P&L':>12}{'WinRate':>10}{'Win/Order':>12}{'PF':>10}{'MaxDD':>10}{'Entries':>10}"
        print(header)
        for tf_name, summary in results:
            wr = f"{summary['win_rate']:.1f}%" if summary["win_rate"] is not None else "N/A"
            wo = f"{summary['wins']}/{summary['closed']}"
            if summary["profit_factor"] is None:
                pf = "N/A"
            elif summary["profit_factor"] == float("inf"):
                pf = "inf"
            else:
                pf = f"{summary['profit_factor']:.2f}"
            print(f"{tf_name:<6}{summary['net_profit']:>12.2f}{wr:>10}{wo:>12}{pf:>10}"
                  f"{summary['max_drawdown']:>10.2f}{summary['entries']:>10}")

        print("\n===== สรุปรายเดือน x TF (net PnL) =====")
        all_months = sorted({m for _, s in results for m in s["monthly"]})
        header2 = "Month   " + "".join(f"{tf:>12}" for tf, _ in results)
        print(header2)
        for month in all_months:
            row = f"{month} "
            for tf_name, summary in results:
                m = summary["monthly"].get(month)
                row += f"{m['net']:>12.2f}" if m else f"{'--':>12}"
            print(row)

    if args.summary_json:
        payload = {tf_name: summary for tf_name, summary in results}
        with open(args.summary_json, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print(f"\nเขียนสรุป JSON ลง {args.summary_json}")


if __name__ == "__main__":
    main()
