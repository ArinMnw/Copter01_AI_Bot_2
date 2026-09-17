import pandas as pd
import numpy as np

df_real = pd.read_csv('reports/s20_304/S20_304_mt5_real.csv')
df_bt = pd.read_csv('reports/s20_304/S20_304_trades.csv')
df_cmp = pd.read_csv('reports/s20_304/S20_304_compare.csv')
df_unmatched_mt5 = pd.read_csv('reports/s20_304/S20_304_mt5_not_match.csv')
df_unmatched_bt = pd.read_csv('reports/s20_304/S20_304_backtest_not_match.csv')

print(f"MT5 Real Trades: {len(df_real)}")
print(f"Backtest Trades: {len(df_bt)}")
print(f"Matched Trades: {len(df_cmp)}")
print(f"Unmatched MT5: {len(df_unmatched_mt5)}")
print(f"Unmatched BT: {len(df_unmatched_bt)}")

print("\n--- Unmatched MT5 Breakdown by TF ---")
print(df_unmatched_mt5['MT5_TF'].value_counts())

print("\n--- Look at M5 Unmatched in MT5 (19 trades) ---")
# Check why M5 did not match
for i, r in df_unmatched_mt5[df_unmatched_mt5['MT5_TF'] == 'M5'].iterrows():
    t_open = r['MT5_Open_Time']
    t_close = r['MT5_Close_Time']
    entry = r['MT5_Entry']
    sl = r['MT5_SL']
    tp = r['MT5_TP']
    comm = r['MT5_Comment']
    pnl = r['MT5_P&L']
    typ = r['MT5_Type']
    # find closest BT trade in time
    print(f"MT5: {t_open} | {typ} {entry} | SL: {sl} TP: {tp} | PnL: ${pnl} | {comm}")
