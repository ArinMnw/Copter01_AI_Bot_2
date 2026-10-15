# -*- coding: utf-8 -*-
"""Backtest Indi1 (3 เส้น H1 + จังหวะ M5) บนข้อมูล MT5 จริง.

ตัวอย่าง:
    python mq5_strategy/indi1/backtest_indi1.py --start 2026-04-01 --end 2026-10-01
    python mq5_strategy/indi1/backtest_indi1.py --months 12 --spread 0.30 --no-be
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HERE = os.path.dirname(os.path.abspath(__file__))
for _path in (_ROOT, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import config
from Indi1_strategy import DEFAULT_CFG, run_backtest

BKK = timezone(timedelta(hours=7))


def parse_bkk(value):
    dt = datetime.fromisoformat(value) if value else datetime.now(BKK)
    return dt.replace(tzinfo=BKK) if dt.tzinfo is None else dt.astimezone(BKK)


def fmt_bkk(dt):
    return dt.astimezone(BKK).strftime("%Y-%m-%d %H:%M:%S")


def bar_time_to_bkk(raw_time):
    # chart=UTC+6 -> raw epoch ของ MT5 ต้องลบ 1 ชม. ถึงเป็นเวลา BKK (ดู mt5_timezone_rule)
    return datetime.fromtimestamp(int(raw_time), tz=BKK) - timedelta(hours=1)


def bkk_to_query(dt):
    return dt + timedelta(hours=1)


def fetch(start_bkk, end_bkk):
    warm = timedelta(days=45)
    if not config.mt5_initialize(mt5):
        raise RuntimeError("MT5 initialization failed")
    try:
        m5 = mt5.copy_rates_range(config.SYMBOL, mt5.TIMEFRAME_M5,
                                  bkk_to_query(start_bkk - warm), bkk_to_query(end_bkk))
        h1 = mt5.copy_rates_range(config.SYMBOL, mt5.TIMEFRAME_H1,
                                  bkk_to_query(start_bkk - warm), bkk_to_query(end_bkk))
    finally:
        mt5.shutdown()
    if m5 is None or h1 is None or len(m5) < 500 or len(h1) < 100:
        raise RuntimeError(f"ข้อมูล MT5 ไม่พอ (M5={0 if m5 is None else len(m5)}, H1={0 if h1 is None else len(h1)})")
    return list(m5), list(h1)


def summarize(trades, start_bkk, end_bkk, init_balance):
    profits = [t["profit"] for t in trades]
    wins = sum(p > 0 for p in profits)
    gw = sum(p for p in profits if p > 0)
    gl = -sum(p for p in profits if p < 0)
    equity = init_balance
    peak = equity
    max_dd = max_dd_pct = 0.0
    for p in profits:
        equity += p
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        max_dd_pct = max(max_dd_pct, (peak - equity) / peak * 100 if peak else 0)
    outcomes = defaultdict(int)
    for t in trades:
        outcomes[t["outcome"]] += 1
    monthly = defaultdict(lambda: {"net": 0.0, "closed": 0, "wins": 0})
    sides = {1: [0, 0.0], -1: [0, 0.0]}
    for t in trades:
        m = monthly[t["exit_time"][:7]]
        m["net"] += t["profit"]; m["closed"] += 1; m["wins"] += t["profit"] > 0
        sides[t["direction"]][0] += 1
        sides[t["direction"]][1] += t["profit"]
    days = max(1.0, (end_bkk - start_bkk).total_seconds() / 86400)
    return {
        "start": fmt_bkk(start_bkk), "end": fmt_bkk(end_bkk), "days": round(days, 1),
        "initial_balance": init_balance, "final_balance": init_balance + sum(profits),
        "closed": len(trades), "wins": wins,
        "win_rate": wins / len(trades) * 100 if trades else None,
        "net_profit": sum(profits), "return_pct": sum(profits) / init_balance * 100,
        "profit_factor": gw / gl if gl else (math.inf if gw else None),
        "max_drawdown": max_dd, "max_drawdown_pct": max_dd_pct,
        "avg_win": gw / wins if wins else None,
        "avg_loss": -gl / (len(trades) - wins) if len(trades) > wins else None,
        "outcomes": dict(outcomes),
        "buy": {"n": sides[1][0], "net": sides[1][1]},
        "sell": {"n": sides[-1][0], "net": sides[-1][1]},
        "monthly": dict(sorted(monthly.items())),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", help="BKK, เช่น 2026-04-01")
    ap.add_argument("--end", help="BKK (default = ตอนนี้)")
    ap.add_argument("--months", type=int, default=6, help="ถ้าไม่ระบุ --start")
    ap.add_argument("--spread", type=float, default=0.20, help="spread เป็นราคา (USD)")
    ap.add_argument("--balance", type=float, default=DEFAULT_CFG["INITIAL_BALANCE"])
    ap.add_argument("--risk", type=float, default=DEFAULT_CFG["RISK_PCT"])
    ap.add_argument("--rr", type=float, default=DEFAULT_CFG["RR"])
    ap.add_argument("--max-entries", type=int, default=DEFAULT_CFG["MAX_ENTRIES_PER_H1"], help="ไม้ต่อสัญญาณ H1 (0 = ไม่จำกัด)")
    ap.add_argument("--sequential", action="store_true", help="ถือได้ทีละไม้")
    ap.add_argument("--no-be", action="store_true", help="ปิด fibo breakeven")
    ap.add_argument("--out", default=os.path.join(_HERE, "indi1_backtest"))
    args = ap.parse_args()

    end = parse_bkk(args.end)
    start = parse_bkk(args.start) if args.start else end - timedelta(days=30 * args.months)
    cfg = {"INITIAL_BALANCE": args.balance, "RISK_PCT": args.risk, "RR": args.rr, "USE_BE": not args.no_be,
           "MAX_ENTRIES_PER_H1": args.max_entries, "CONCURRENT": not args.sequential}

    m5, h1 = fetch(start, end)
    start_ts = int(bkk_to_query(start).timestamp())
    start_bar = next((i for i, b in enumerate(m5) if int(b["time"]) >= start_ts), None)
    if start_bar is None or start_bar < 300:
        raise RuntimeError(f"warm-up ไม่พอ (start_bar={start_bar})")

    raw, extra = run_backtest(m5, cfg, spread=args.spread, htf_bars=h1, start_bar=start_bar)
    trades = []
    for t in raw:
        trades.append({
            "entry_time": fmt_bkk(bar_time_to_bkk(m5[t["entry_bar"]]["time"])),
            "exit_time": fmt_bkk(bar_time_to_bkk(m5[t["exit_bar"]]["time"])),
            **{k: t[k] for k in ("direction", "lot", "entry", "initial_sl", "sl", "tp", "exit_price", "outcome", "profit", "balance")},
        })
    res = summarize(trades, start, end, args.balance)
    res["signals"] = {k: v for k, v in extra.items() if k not in ("entries", "open_positions")}
    res["spread"] = args.spread
    res["bars"] = {"m5": len(m5), "h1": len(h1)}

    with open(args.out + ".json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2, default=str)
    if trades:
        with open(args.out + "_trades.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(trades[0]))
            w.writeheader(); w.writerows(trades)
    print(json.dumps(res, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
