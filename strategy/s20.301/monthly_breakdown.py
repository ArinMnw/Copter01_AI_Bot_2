# -*- coding: utf-8 -*-
"""monthly_breakdown.py for S20.301"""
import pandas as pd
import os

def main():
    csv_path = os.path.join(os.path.dirname(__file__), "S20_301_monthly.csv")
    if not os.path.exists(csv_path):
        print("S20_301_monthly.csv not found. Running verification first...")
        import run_s20_301_m5_verified
        run_s20_301_m5_verified.main()

    df = pd.read_csv(csv_path)
    print("=" * 80)
    print(" S20.301 MONTHLY PERFORMANCE BREAKDOWN (STRICT 0.01 LOT)")
    print("=" * 80)
    print(df.to_string(index=False))
    print("=" * 80)
    print(f"Total Net Profit: ${df['pnl'].sum():,.2f}")

if __name__ == "__main__":
    main()
