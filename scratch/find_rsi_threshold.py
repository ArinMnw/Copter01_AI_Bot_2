import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import sys

df = pd.read_csv('d:/Project/Copter01_AI_Bot_2/strategy/s20.13/excel/s20_13_sim_trades.csv')

if not mt5.initialize():
    sys.exit()

rates = mt5.copy_rates_from_pos("XAUUSD.iux", mt5.TIMEFRAME_H1, 0, 1000)
mt5_df = pd.DataFrame(rates)
mt5_df['time'] = pd.to_datetime(mt5_df['time'], unit='s')

delta = mt5_df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
mt5_df['RSI'] = 100 - (100 / (1 + rs))

df['Time (BKK)'] = pd.to_datetime(df['Time (BKK)'])
df['Server_Time'] = df['Time (BKK)'] - pd.Timedelta(hours=7)

merged = pd.merge(df, mt5_df, left_on='Server_Time', right_on='time', how='left')

print("=== RSI Distribution ===")
for r in ['TP', 'BE', 'SL']:
    print(f"\n--- Reason: {r} ---")
    for t in ['BUY', 'SELL']:
        subset = merged[(merged['Reason'] == r) & (merged['Type'] == t)]
        print(f"Type: {t} | Count: {len(subset)}")
        if not subset.empty:
            print(subset['RSI'].describe(percentiles=[0.25, 0.5, 0.75, 0.9, 0.95]))

mt5.shutdown()
