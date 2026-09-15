# -*- coding: utf-8 -*-
"""Walk-forward (dual-window) check สำหรับ top config ที่ได้จาก sweep_s434.py —
เช็คว่า MIN_TP_ATR_MULT floor ที่ดูดีบน full-year ผ่านทั้งสองครึ่งปีจริงหรือ
overfit เฉพาะครึ่งใดครึ่งหนึ่ง

Usage:
    python wf_s434.py
"""
from __future__ import annotations

import math
import os
import sys
from datetime import timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from backtest_s434 import parse_bkk, prepare_rates, _lookback_bars, bar_time_to_bkk
from strategy434 import DEFAULT_CFG, run_backtest

SPREAD = 0.20
LOT = 0.01
DAYS = 365

# top config ต่อ TF จาก sweep_s434_result_*.json (เลือกตัวที่ PF สูงสุดและ n
# ไม่บางเกินไป)
CANDIDATES = {
    "M30": {"ATR_MULT": 1.5, "MIN_TP_ATR_MULT": 3.0},
    "H1":  {"ATR_MULT": 1.0, "MIN_TP_ATR_MULT": 2.0},
    "H4":  {"ATR_MULT": 1.0, "MIN_TP_ATR_MULT": 3.0},
    "H12": {"ATR_MULT": 2.0, "MIN_TP_ATR_MULT": 0.75},
    "D1":  {"ATR_MULT": 1.0, "MIN_TP_ATR_MULT": 1.5},
}


def _summarize(bars, trades, start_bkk, end_bkk):
    profits = [t["profit"] for t in trades if start_bkk <= bar_time_to_bkk(int(bars[t["entry_bar"]]["time"])) < end_bkk]
    wins = sum(p > 0.0 for p in profits)
    gross_win = sum(p for p in profits if p > 0.0)
    gross_loss = -sum(p for p in profits if p < 0.0)
    net = sum(profits)
    pf = gross_win / gross_loss if gross_loss else (math.inf if gross_win else None)
    return {"closed": len(profits), "win_rate": wins / len(profits) * 100.0 if profits else None,
            "net_profit": net, "profit_factor": pf}


def main():
    end_bkk = parse_bkk(None)
    full_start = end_bkk - timedelta(days=DAYS)
    mid_bkk = end_bkk - timedelta(days=DAYS / 2.0)
    contract_multiplier = 100.0 * LOT

    print(f"{'TF':<5}{'window':<10}{'Net':>12}{'PF':>8}{'WinRate':>9}{'Closed':>8}")
    for tf_name, cfg_over in CANDIDATES.items():
        cfg = dict(DEFAULT_CFG)
        cfg.update(cfg_over)
        lookback_bars = _lookback_bars(cfg)
        bars_raw = prepare_rates(tf_name, full_start, end_bkk, lookback_bars)
        trades, _extra = run_backtest(bars_raw, cfg, spread=SPREAD, contract_multiplier=contract_multiplier)

        for label, w_start, w_end in (("H1(first)", full_start, mid_bkk), ("H2(second)", mid_bkk, end_bkk),
                                       ("FULL", full_start, end_bkk)):
            s = _summarize(bars_raw, trades, w_start, w_end)
            pf = s["profit_factor"]
            pf_str = f"{pf:.2f}" if isinstance(pf, (int, float)) and pf != math.inf else str(pf)
            wr = f"{s['win_rate']:.1f}%" if s["win_rate"] is not None else "N/A"
            print(f"{tf_name:<5}{label:<10}{s['net_profit']:>12.2f}{pf_str:>8}{wr:>9}{s['closed']:>8}   cfg={cfg_over}")
        print()


if __name__ == "__main__":
    main()
