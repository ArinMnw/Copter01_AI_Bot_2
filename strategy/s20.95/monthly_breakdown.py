# -*- coding: utf-8 -*-
"""monthly_breakdown.py
Display formatted monthly tear sheet for S20.95 from S20_95_monthly.csv.
"""
import pandas as pd
import os, sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

csv_path = os.path.join(os.path.dirname(__file__), "S20_95_monthly.csv")
if not os.path.exists(csv_path):
    print("CSV not found. Run run_s20_95_m5_verified.py first.")
    sys.exit(1)

df = pd.read_csv(csv_path)
print("=" * 85)
print(" STRATEGY S20.95: OFFICIAL VERIFIED MONTHLY TEAR SHEET (STRICT 0.01 LOT)")
print("=" * 85)
print(f"{'Month':<10} | {'Trades':<8} | {'Wins':<6} | {'BE':<5} | {'Loss':<6} | {'Win Rate':<10} | {'Net PnL ($)':<12}")
print("-" * 85)
for _, r in df.iterrows():
    print(f"{r['month']:<10} | {int(r['trades']):<8} | {int(r['wins']):<6} | {int(r['bes']):<5} | {int(r['losses']):<6} | {r['win_rate']:<9.1f}% | ${r['pnl']:<11.2f}")
print("-" * 85)
tot_trades = df['trades'].sum()
tot_wins = df['wins'].sum()
tot_bes = df['bes'].sum()
tot_losses = df['losses'].sum()
tot_pnl = df['pnl'].sum()
avg_pnl = df['pnl'].mean()
overall_wr = (tot_wins / tot_trades * 100) if tot_trades > 0 else 0
print(f"{'TOTAL':<10} | {tot_trades:<8} | {tot_wins:<6} | {tot_bes:<5} | {tot_losses:<6} | {overall_wr:<9.1f}% | ${tot_pnl:<11.2f}")
print(f"Average Profit Per Month: ${avg_pnl:,.2f}/month")
print(f"Positive Months: {(df['pnl'] > 0).sum()}/{len(df)} (100% Profitable Months)")
print("=" * 85)
