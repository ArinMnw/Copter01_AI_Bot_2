# -*- coding: utf-8 -*-
"""Sweep MIN_TP_ATR_MULT (TP floor) x ATR_MULT (SL) สำหรับ S434 ทุก TF (365 วัน)
ดึงข้อมูลราคาครั้งเดียวต่อ TF แล้ววน cfg เพื่อประหยัดเวลา MT5 fetch

Usage:
    python sweep_s434.py
    python sweep_s434.py M1 M5 M15
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from backtest_s434 import DEFAULT_DAYS, parse_bkk, prepare_rates, _lookback_bars, bar_time_to_bkk
from strategy434 import DEFAULT_CFG, run_backtest

TF_LIST = tuple(sys.argv[1:]) or ("M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1")
MIN_TP_ATR_MULTS = (0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0)
ATR_MULTS = (1.0, 1.5, 2.0)

SPREAD = 0.20
LOT = 0.01
DAYS = 365


def _summarize(bars, trades, start_bkk, end_bkk):
    profits = [t["profit"] for t in trades if bar_time_to_bkk(int(bars[t["entry_bar"]]["time"])) >= start_bkk]
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
        "closed": len(profits), "wins": wins,
        "win_rate": wins / len(profits) * 100.0 if profits else None,
        "net_profit": net, "profit_factor": pf, "max_drawdown": max_dd,
    }


def main():
    end_bkk = parse_bkk(None)
    start_bkk = end_bkk - timedelta(days=DAYS)
    contract_multiplier = 100.0 * LOT

    results = {}
    for tf_name in TF_LIST:
        print(f"\n===== TF={tf_name}: fetching bars =====")
        lookback_bars = _lookback_bars(DEFAULT_CFG)
        bars_raw = prepare_rates(tf_name, start_bkk, end_bkk, lookback_bars)
        print(f"  {len(bars_raw)} bars fetched")

        tf_results = []
        for atr_mult in ATR_MULTS:
            for min_tp_mult in MIN_TP_ATR_MULTS:
                cfg = dict(DEFAULT_CFG)
                cfg["ATR_MULT"] = atr_mult
                cfg["MIN_TP_ATR_MULT"] = min_tp_mult
                trades, extra = run_backtest(bars_raw, cfg, spread=SPREAD,
                                              contract_multiplier=contract_multiplier)
                summary = _summarize(bars_raw, trades, start_bkk, end_bkk)
                summary.update({"atr_mult": atr_mult, "min_tp_atr_mult": min_tp_mult,
                                 "entries": extra.get("entries")})
                tf_results.append(summary)

        tf_results.sort(key=lambda s: (s["profit_factor"] if s["profit_factor"] not in (None, math.inf) else -1),
                         reverse=True)
        results[tf_name] = tf_results

        print(f"  Top 10 by PF:")
        print(f"  {'ATR_MULT':>9}{'MinTP_ATR':>11}{'Net':>12}{'PF':>8}{'WinRate':>9}{'Closed':>8}{'MaxDD':>10}")
        for s in tf_results[:10]:
            pf = s["profit_factor"]
            pf_str = f"{pf:.2f}" if isinstance(pf, (int, float)) and pf != math.inf else str(pf)
            wr = f"{s['win_rate']:.1f}%" if s["win_rate"] is not None else "N/A"
            print(f"  {s['atr_mult']:>9}{s['min_tp_atr_mult']:>11}{s['net_profit']:>12.2f}{pf_str:>8}{wr:>9}{s['closed']:>8}{s['max_drawdown']:>10.2f}")

    out_name = f"sweep_s434_result_{'_'.join(TF_LIST)}.json"
    with open(os.path.join(_HERE, out_name), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=lambda o: None if o == math.inf else o)
    print(f"\nเขียนผล sweep ลง {out_name}")


if __name__ == "__main__":
    main()
