# -*- coding: utf-8 -*-
"""monthly_breakdown.py — Detailed month-by-month tear sheet for S20.26."""

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

import strategy20_26
import backtest_s20_26_runner


def run_breakdown():
    if not backtest_s20_26_runner.init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    symbol_silver = "XAGUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    for tf_str, tf_mt5 in [("M30", mt5.TIMEFRAME_M30), ("M15", mt5.TIMEFRAME_M15)]:
        print(f"\n{'='*75}")
        print(f" S20.26 QUAD-ENGINE APEX CONFLUENCE — MONTHLY TEAR SHEET ({tf_str})")
        print(f"{'='*75}")

        g_rates = mt5.copy_rates_range(symbol_gold, tf_mt5, start_dt, now)
        s_rates = mt5.copy_rates_range(symbol_silver, tf_mt5, start_dt, now)

        df = strategy20_26.compute_indicators_df(g_rates, s_rates)
        res = backtest_s20_26_runner.simulate_s20_26(g_rates, df, mode="all_confluence", total_lot=0.02, tf_name=tf_str)

        records = res["records"]
        t_df = pd.DataFrame(records)
        if t_df.empty:
            continue

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
        out_csv = os.path.join(current_dir, f"S20_26_{tf_str}_monthly.csv")
        monthly.to_csv(out_csv, index=False)
        print(f"Saved: {out_csv}")

    mt5.shutdown()


if __name__ == "__main__":
    run_breakdown()
