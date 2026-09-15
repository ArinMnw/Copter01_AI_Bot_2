# -*- coding: utf-8 -*-
"""monthly_breakdown.py for S20.241"""
import pandas as pd
import os

def main():
    csv_path = os.path.join(os.path.dirname(__file__), "S20_241_monthly.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        print("="*80)
        print(" S20.241 MONTHLY PERFORMANCE BREAKDOWN (STRICT 0.01 LOT)")
        print("="*80)
        print(df.to_string(index=False))
        print("="*80)
        print(f"Total Net Profit: ${df['pnl'].sum():,.2f}")
    else:
        print("CSV not found. Run runner first.")

if __name__ == "__main__":
    main()
