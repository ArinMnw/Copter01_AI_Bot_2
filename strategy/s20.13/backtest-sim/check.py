import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime, timedelta

mt5.initialize()
now = datetime.now()
start = now - timedelta(days=150)
rates = mt5.copy_rates_range("XAUUSD.iux", mt5.TIMEFRAME_H1, start, now)
df = pd.DataFrame(rates)
df['Time (BKK)'] = [datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M') for t in df['time']]

df['atr'] = np.maximum(df['high']-df['low'], np.maximum(np.abs(df['high']-df['close'].shift()), np.abs(df['low']-df['close'].shift()))).rolling(14).mean()

df_trades = pd.read_csv('s20_13_13_trades.csv')
merged = pd.merge(df_trades, df, on='Time (BKK)', how='left')

print("Wins:", len(merged[merged['Reason'] == 'TP']))
print("Losses:", len(merged[merged['Reason'] == 'SL']))

print("Wins (ATR < 25):", len(merged[(merged['Reason'] == 'TP') & (merged['atr'] < 25)]))
print("Losses (ATR < 25):", len(merged[(merged['Reason'] == 'SL') & (merged['atr'] < 25)]))

mt5.shutdown()
