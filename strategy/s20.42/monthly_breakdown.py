# -*- coding: utf-8 -*-
"""monthly_breakdown.py
Display and export detailed monthly performance for Strategy S20.42 on Gold (XAUUSD.iux).
"""

import pandas as pd
import os

def display_monthly():
    csv_path = os.path.join(os.path.dirname(__file__), "S20_42_monthly.csv")
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found. Please run run_s20_42_m5_verified.py first.")
        return

    df = pd.read_csv(csv_path)
    print("=" * 75)
    print(" STRATEGY S20.42: OFFICIAL MONTHLY PERFORMANCE BREAKDOWN (0.01 LOT)")
    print("=" * 75)
    print(f"{'Month':8s} | {'Trades':6s} | {'Wins':4s} | {'BEs':4s} | {'Losses':6s} | {'WinRate':7s} | {'Net PnL ($)':11s}")
    print("-" * 75)
    for _, row in df.iterrows():
        print(f"{row['month']:8s} | {int(row['trades']):6d} | {int(row['wins']):4d} | {int(row['bes']):4d} | {int(row['losses']):6d} | {row['win_rate']:6.1f}% | ${row['pnl']:10.2f}")
    print("-" * 75)
    total_trades = df['trades'].sum()
    total_wins = df['wins'].sum()
    total_bes = df['bes'].sum()
    total_losses = df['losses'].sum()
    total_pnl = df['pnl'].sum()
    overall_wr = (total_wins / total_trades * 100.0) if total_trades > 0 else 0.0
    print(f"{'TOTAL':8s} | {int(total_trades):6d} | {int(total_wins):4d} | {int(total_bes):4d} | {int(total_losses):6d} | {overall_wr:6.1f}% | ${total_pnl:10.2f}")
    print(f"Average Monthly Profit: ${total_pnl / len(df):,.2f} / month")
    print("=" * 75)

if __name__ == "__main__":
    display_monthly()
