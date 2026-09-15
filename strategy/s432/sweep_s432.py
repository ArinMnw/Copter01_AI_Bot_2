# -*- coding: utf-8 -*-
"""สวีปหา config SL/TP ที่ดีขึ้นของ S432 (Market Path Forecast) เฉพาะ TF ที่ระบุ
(default M15,H1) — สวีป TP_BASE_MULT / SL_ATR_MULT / SL_BASE_MULT (สูตร SL/TP
เดิม: tp=close+side*baseDistance*TP_BASE_MULT, sl=close-side*max(atr*
SL_ATR_MULT, baseDistance*SL_BASE_MULT)) บนข้อมูลเต็มปี (in-sample) แล้วเช็ค
robustness ของ top-N ด้วย dual-window (ครึ่งปีแรก/หลัง) ก่อนสรุป — ไม่ผ่าน
dual-window (บวกไม่ครบสองครึ่ง) = ตัดทิ้งแม้ full-year เลขจะสวย

Usage:
    python sweep_s432.py --days 365 --tf M15,H1
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import sys
from datetime import timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from backtest_s432 import DEFAULT_CFG as RUNNER_DEFAULT  # noqa: F401 (import ordering)
from backtest_s432 import _lookback_bars, parse_bkk, prepare_rates
from strategy432 import DEFAULT_CFG, run_backtest

TP_GRID = [0.6, 0.8, 1.0, 1.3, 1.6, 2.0]
SL_ATR_GRID = [0.75, 1.0, 1.5, 2.0, 2.5]
SL_BASE_GRID = [0.20, 0.40, 0.60]


def _summarize(trades, calendar_days):
    profits = [t["profit"] for t in trades]
    wins = sum(p > 0.0 for p in profits)
    gross_win = sum(p for p in profits if p > 0.0)
    gross_loss = -sum(p for p in profits if p < 0.0)
    net = sum(profits)
    equity = peak = max_dd = 0.0
    for p in profits:
        equity += p
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    pf = gross_win / gross_loss if gross_loss else (math.inf if gross_win else None)
    return {
        "trades": len(trades), "wins": wins,
        "win_rate": wins / len(trades) * 100.0 if trades else None,
        "net": net, "pnl_per_day": net / calendar_days if calendar_days else None,
        "pf": pf, "max_dd": max_dd,
    }


def _run(bars_raw, cfg, spread, contract_multiplier, start_bkk, end_bkk, bars_for_time=None):
    trades_raw, extra = run_backtest(bars_raw, cfg, spread=spread, contract_multiplier=contract_multiplier)
    bars = bars_for_time or bars_raw
    trades = []
    for t in trades_raw:
        entry_time_raw = int(bars[t["entry_bar"]]["time"])
        from backtest_s432 import bar_time_to_bkk
        entry_time = bar_time_to_bkk(entry_time_raw)
        if entry_time < start_bkk or entry_time >= end_bkk:
            continue
        trades.append(t)
    calendar_days = max(1.0, (end_bkk - start_bkk).total_seconds() / 86400.0)
    return _summarize(trades, calendar_days)


def sweep_tf(tf_name, spread, lot, start_bkk, end_bkk, top_n=8):
    detector_cfg = dict(DEFAULT_CFG)
    lookback_bars = _lookback_bars(detector_cfg)
    bars_raw = prepare_rates(tf_name, start_bkk, end_bkk, lookback_bars)
    contract_multiplier = 100.0 * lot

    grid = list(itertools.product(TP_GRID, SL_ATR_GRID, SL_BASE_GRID))
    print(f"[{tf_name}] full-year sweep: {len(grid)} combos ...")

    results = []
    for tp_mult, sl_atr, sl_base in grid:
        cfg = dict(DEFAULT_CFG)
        cfg["TP_BASE_MULT"] = tp_mult
        cfg["SL_ATR_MULT"] = sl_atr
        cfg["SL_BASE_MULT"] = sl_base
        summary = _run(bars_raw, cfg, spread, contract_multiplier, start_bkk, end_bkk)
        results.append({
            "tp_mult": tp_mult, "sl_atr": sl_atr, "sl_base": sl_base,
            **summary,
        })

    # เกณฑ์คัดกรองแรก: ต้องมีไม้พอสมควร (กัน overfit เพราะ n น้อยเกินไป) + PF ไม่ null
    viable = [r for r in results if r["trades"] >= 60 and r["pf"] is not None]
    viable.sort(key=lambda r: (r["pf"] if r["pf"] != math.inf else 1e9), reverse=True)

    print(f"[{tf_name}] top {top_n} by full-year PF (trades>=60):")
    header = f"{'TP':>5}{'SLatr':>7}{'SLbase':>8}{'Net':>10}{'PF':>7}{'WR':>7}{'MaxDD':>9}{'Trades':>8}"
    print(header)
    for r in viable[:top_n]:
        pf_str = f"{r['pf']:.2f}" if r["pf"] != math.inf else "inf"
        wr_str = f"{r['win_rate']:.1f}%" if r["win_rate"] is not None else "N/A"
        print(f"{r['tp_mult']:>5.1f}{r['sl_atr']:>7.2f}{r['sl_base']:>8.2f}"
              f"{r['net']:>10.2f}{pf_str:>7}{wr_str:>7}{r['max_dd']:>9.2f}{r['trades']:>8}")

    # --- dual-window robustness ของ top_n ---
    mid_bkk = start_bkk + (end_bkk - start_bkk) / 2
    print(f"\n[{tf_name}] dual-window robustness check (top {top_n}):")
    header2 = f"{'TP':>5}{'SLatr':>7}{'SLbase':>8}{'NetH1':>10}{'PFh1':>7}{'NetH2':>10}{'PFh2':>7}{'ผ่าน':>6}"
    print(header2)
    robust = []
    for r in viable[:top_n]:
        cfg = dict(DEFAULT_CFG)
        cfg["TP_BASE_MULT"] = r["tp_mult"]
        cfg["SL_ATR_MULT"] = r["sl_atr"]
        cfg["SL_BASE_MULT"] = r["sl_base"]
        s1 = _run(bars_raw, cfg, spread, contract_multiplier, start_bkk, mid_bkk)
        s2 = _run(bars_raw, cfg, spread, contract_multiplier, mid_bkk, end_bkk)
        pf1 = s1["pf"] if s1["pf"] is not None else 0.0
        pf2 = s2["pf"] if s2["pf"] is not None else 0.0
        passed = s1["net"] > 0 and s2["net"] > 0 and s1["trades"] >= 20 and s2["trades"] >= 20
        pf1_str = f"{pf1:.2f}" if pf1 != math.inf else "inf"
        pf2_str = f"{pf2:.2f}" if pf2 != math.inf else "inf"
        print(f"{r['tp_mult']:>5.1f}{r['sl_atr']:>7.2f}{r['sl_base']:>8.2f}"
              f"{s1['net']:>10.2f}{pf1_str:>7}{s2['net']:>10.2f}{pf2_str:>7}{'YES' if passed else 'no':>6}")
        if passed:
            robust.append({**r, "net_h1": s1["net"], "pf_h1": pf1, "net_h2": s2["net"], "pf_h2": pf2})

    return results, robust


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--tf", default="M15,H1")
    parser.add_argument("--spread", type=float, default=0.20)
    parser.add_argument("--balance", type=float, default=100.0)
    parser.add_argument("--lot", type=float, default=None)
    parser.add_argument("--top", type=int, default=8)
    args = parser.parse_args()

    lot = args.lot if args.lot is not None else args.balance / 10000.0
    end_bkk = parse_bkk(None)
    start_bkk = end_bkk - timedelta(days=args.days)

    all_robust = {}
    for tf_name in args.tf.split(","):
        tf_name = tf_name.strip()
        print(f"\n===== TF={tf_name} =====")
        _results, robust = sweep_tf(tf_name, args.spread, lot, start_bkk, end_bkk, top_n=args.top)
        all_robust[tf_name] = robust

    print("\n===== สรุป config ที่ผ่าน dual-window robustness =====")
    for tf_name, robust in all_robust.items():
        print(f"\n[{tf_name}]")
        if not robust:
            print("  ไม่มี config ไหนผ่าน dual-window (บวกทั้งสองครึ่ง + trades>=20/ครึ่ง)")
            continue
        robust.sort(key=lambda r: min(r["pf_h1"] if r["pf_h1"] != math.inf else 1e9,
                                       r["pf_h2"] if r["pf_h2"] != math.inf else 1e9), reverse=True)
        for r in robust:
            print(f"  TP_BASE_MULT={r['tp_mult']} SL_ATR_MULT={r['sl_atr']} SL_BASE_MULT={r['sl_base']} "
                  f"| full-year net={r['net']:.2f} pf={r['pf']:.2f} trades={r['trades']} "
                  f"| H1net={r['net_h1']:.2f} pfH1={r['pf_h1']:.2f} H2net={r['net_h2']:.2f} pfH2={r['pf_h2']:.2f}")


if __name__ == "__main__":
    main()
