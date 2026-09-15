# -*- coding: utf-8 -*-
"""monthly_breakdown.py for S20.304"""
import pandas as pd
import os

def main():
    csv_path = os.path.join(os.path.dirname(__file__), "S20_304_monthly.csv")
    df = pd.read_csv(csv_path)
    print("=" * 105)
    print(" S20.304 DUAL-ASSET MONTHLY BREAKDOWN (GOLD + SILVER, STRICT 0.01 LOT EACH)")
    print("=" * 105)
    print(df.to_string(index=False))
    print("=" * 105)
    print(f"Total Net Profit: ${df['total_pnl'].sum():,.2f}")

if __name__ == "__main__":
    main()
