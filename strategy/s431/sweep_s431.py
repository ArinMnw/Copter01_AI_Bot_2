# -*- coding: utf-8 -*-
"""สวีป S431 (Breakout Pattern Setup) ทุก TF x หลายหน้าต่างเวลา (30/60/90/120/
180/270/365 วัน) — เรียก backtest_tf() ตรงๆ จาก backtest_s431.py ต่อ
(tf, days) หนึ่งคู่ ไม่ parallel (แต่ละรันเร็วมากอยู่แล้ว ~วินาที) พิมพ์ตาราง
สรุปต่อ TF แล้วเขียน sweep_s431_result.json เก็บผลดิบทั้งหมดไว้ด้วย

Usage:
    python sweep_s431.py
    python sweep_s431.py --tf M5 --windows 30 60 90
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from backtest_s431 import TF_MAP, backtest_tf, parse_bkk

DEFAULT_WINDOWS = (30, 60, 90, 120, 180, 270, 365)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tf", nargs="+", choices=tuple(TF_MAP), default=list(TF_MAP))
    parser.add_argument("--windows", nargs="+", type=int, default=list(DEFAULT_WINDOWS))
    parser.add_argument("--balance", type=float, default=100.0)
    parser.add_argument("--spread", type=float, default=0.20)
    parser.add_argument("--out", default=os.path.join(_HERE, "sweep_s431_result.json"))
    args = parser.parse_args()

    lot = args.balance / 10000.0
    end_bkk = parse_bkk(None)

    all_results = {}
    for tf_name in args.tf:
        print(f"\n===== TF={tf_name} =====")
        header = f"{'Days':>6}{'P&L':>12}{'WinRate':>10}{'Win/Order':>12}{'PF':>10}{'MaxDD':>10}{'Patterns':>10}"
        print(header)
        tf_results = []
        for days in args.windows:
            start_bkk = end_bkk - timedelta(days=days)
            try:
                summary, _trades = backtest_tf(tf_name, args.spread, lot, start_bkk, end_bkk)
            except RuntimeError as exc:
                print(f"{days:>6}  ข้าม: {exc}")
                continue
            wr = f"{summary['win_rate']:.1f}%" if summary["win_rate"] is not None else "N/A"
            wo = f"{summary['wins']}/{summary['closed']}"
            if summary["profit_factor"] is None:
                pf = "N/A"
            elif summary["profit_factor"] == float("inf"):
                pf = "inf"
            else:
                pf = f"{summary['profit_factor']:.2f}"
            print(f"{days:>6}{summary['net_profit']:>12.2f}{wr:>10}{wo:>12}{pf:>10}"
                  f"{summary['max_drawdown']:>10.2f}{summary['total_patterns']:>10}")
            tf_results.append({"days": days, **summary})
        all_results[tf_name] = tf_results

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(all_results, handle, ensure_ascii=False, indent=2, default=str)
    print(f"\nเขียนผลดิบลง {args.out}")

    # --- สรุปว่า TF ไหนกำไรทุกหน้าต่างที่รันได้ (เกณฑ์คัดกรองมาตรฐานของโปรเจกต์) ---
    print("\n===== สรุป: TF ไหนบวกทุกหน้าต่าง =====")
    for tf_name, results in all_results.items():
        if not results:
            print(f"{tf_name}: ไม่มีข้อมูลพอ (ทุกหน้าต่างข้าม)")
            continue
        all_positive = all(r["net_profit"] > 0 for r in results)
        n_windows = len(results)
        n_positive = sum(1 for r in results if r["net_profit"] > 0)
        verdict = "✅ บวกทุกหน้าต่าง" if all_positive else f"❌ บวกแค่ {n_positive}/{n_windows}"
        print(f"{tf_name}: {verdict}")


if __name__ == "__main__":
    main()
