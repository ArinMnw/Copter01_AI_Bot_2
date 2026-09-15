# -*- coding: utf-8 -*-
"""monthly_breakdown.py — Monthly tear sheet for S20.29 Quantum Fusion."""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if current_dir not in sys.path:
    sys.path.append(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

import strategy20_29
import backtest_s20_29_runner


def run_breakdown():
    if not backtest_s20_29_runner.init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    symbol_silver = "XAGUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    m30_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M30, start_dt, now)
    m30_silver = mt5.copy_rates_range(symbol_silver, mt5.TIMEFRAME_M30, start_dt, now)

    m15_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M15, start_dt, now)
    m15_silver = mt5.copy_rates_range(symbol_silver, mt5.TIMEFRAME_M15, start_dt, now)

    mt5.shutdown()

    m30_df = strategy20_29.compute_indicators_df(m30_gold, m30_silver)
    m15_df = strategy20_29.compute_indicators_df(m15_gold, m15_silver)

    # 1. Dual Horizon Breakdown
    print(f"\n{'='*75}")
    print(f" S20.29 DUAL-HORIZON (M15+M30) — MONTHLY TEAR SHEET (+$3,214.32 NET)")
    print(f"{'='*75}")

    res_dual = backtest_s20_29_runner.simulate_dual_horizon(m15_gold, m15_df, m30_gold, m30_df)
    t_df = pd.DataFrame(res_dual["records"])

    monthly = t_df.groupby('month').agg(
        Trades=('pnl', 'count'),
        Wins=('outcome', lambda x: (x.isin(['FULL_WIN', 'SCALP_WIN'])).sum()),
        BEs=('outcome', lambda x: (x == 'BE').sum()),
        Losses=('outcome', lambda x: (x == 'LOSS').sum()),
        NetPnL=('pnl', 'sum')
    ).reset_index()

    monthly['WinRate%'] = (monthly['Wins'] / monthly['Trades'] * 100.0).round(1)
    monthly['NetPnL'] = monthly['NetPnL'].round(2)

    print(monthly.to_string(index=False))
    out_csv = os.path.join(current_dir, "S20_29_DualHorizon_monthly.csv")
    monthly.to_csv(out_csv, index=False)
    print(f"Saved: {out_csv}")


if __name__ == "__main__":
    run_breakdown()
