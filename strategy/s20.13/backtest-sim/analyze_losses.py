import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import numpy as np
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from config import SYMBOL

if not mt5.initialize():
    print("MT5 Init failed")
    sys.exit()

df_trades = pd.read_csv("s20_13_13_trades.csv")
now = datetime.now()
start = now - timedelta(days=150)
rates = mt5.copy_rates_range("XAUUSD.iux", mt5.TIMEFRAME_H1, start, now)
df_rates = pd.DataFrame(rates)
df_rates['time_dt'] = pd.to_datetime(df_rates['time'], unit='s')
# adjust MT5 time to BKK (assuming MT5 is UTC+2 or something)
# The BKK time in CSV is datetime.fromtimestamp(rates[i-1]['time']).strftime("%Y-%m-%d %H:%M")
# So we can just match exactly by using that string formatting!
df_rates['Time (BKK)'] = [datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M") for t in df_rates['time']]

# Calculate indicators
high_low = df_rates['high'] - df_rates['low']
high_close = np.abs(df_rates['high'] - df_rates['close'].shift())
low_close = np.abs(df_rates['low'] - df_rates['close'].shift())
tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
df_rates['atr'] = tr.rolling(window=14).mean()

delta = df_rates['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
df_rates['rsi'] = 100 - (100 / (1 + rs))

df_rates['ema_50'] = df_rates['close'].ewm(span=50, adjust=False).mean()
df_rates['ema_200'] = df_rates['close'].ewm(span=200, adjust=False).mean()
df_rates['dist_ema50'] = np.abs(df_rates['close'] - df_rates['ema_50']) / df_rates['atr']

df_rates['body'] = np.abs(df_rates['close'] - df_rates['open'])
df_rates['upper_wick'] = df_rates['high'] - np.maximum(df_rates['open'], df_rates['close'])
df_rates['lower_wick'] = np.minimum(df_rates['open'], df_rates['close']) - df_rates['low']
df_rates['range'] = df_rates['high'] - df_rates['low']
df_rates['lower_wick_pct'] = df_rates['lower_wick'] / df_rates['range']
df_rates['upper_wick_pct'] = df_rates['upper_wick'] / df_rates['range']

# For sweep depth, we need a loop or rolling
sweep_depths = []
for i in range(len(df_rates)):
    if i < 15:
        sweep_depths.append(np.nan)
        continue
    lookback = df_rates.iloc[i-15:i-4]
    local_low = lookback['low'].min()
    local_high = lookback['high'].max()
    sweep_depth = 0
    if df_rates['close'].iloc[i] > df_rates['open'].iloc[i]: # Bullish
        sweep_bot = min(df_rates['low'].iloc[i-3:i+1].min(), df_rates['low'].iloc[i])
        sweep_depth = local_low - sweep_bot
    else:
        sweep_top = max(df_rates['high'].iloc[i-3:i+1].max(), df_rates['high'].iloc[i])
        sweep_depth = sweep_top - local_high
    sweep_depths.append(sweep_depth)
df_rates['sweep_depth'] = sweep_depths

df_rates['sl_dist_buy'] = df_rates['close'] - (df_rates['low'] - df_rates['atr'])
df_rates['sl_dist_sell'] = (df_rates['high'] + df_rates['atr']) - df_rates['close']
df_rates['sl_dist'] = np.nan
df_rates['fuel'] = df_rates['atr'] * 2.6 * np.sqrt(720 / 60)
df_rates['tp'] = df_rates['low'] + df_rates['fuel']
df_rates['tp_dist'] = df_rates['tp'] - df_rates['close']
df_rates['rr'] = df_rates['tp_dist'] / df_rates['sl_dist']

df_rates['sweep_wick_pct'] = np.nan

# Merge
merged = pd.merge(df_trades, df_rates, on="Time (BKK)", how="left")

merged['sweep_wick_pct'] = np.where(merged['Type'] == 'BUY', merged['lower_wick_pct'], merged['upper_wick_pct'])
merged['sl_dist'] = np.where(merged['Type'] == 'BUY', merged['sl_dist_buy'], merged['sl_dist_sell'])
merged['sl_dist_atr'] = merged['sl_dist'] / merged['atr']

merged['is_valid_setup'] = (merged['body'] >= 0.5 * merged['atr']) | (merged['sweep_wick_pct'] >= 0.5)

merged['is_win'] = merged['Reason'] == 'TP'

print("--- WINS ---")
wins = merged[merged['is_win']]
print(f"Count: {len(wins)}")
print(f"Avg ATR: {wins['atr'].mean():.2f}")
print(f"Avg RSI: {wins['rsi'].mean():.2f}")
print(f"Avg Body/ATR: {(wins['body'] / wins['atr']).mean():.2f}")
print(f"Avg Sweep/ATR: {(wins['sweep_depth'] / wins['atr']).mean():.2f}")
print(f"Avg Body/Range: {(wins['body'] / wins['range']).mean():.2f}")
print(f"Avg Dist EMA50/ATR: {wins['dist_ema50'].mean():.2f}")
print(f"Avg Sweep Wick Pct: {wins['sweep_wick_pct'].mean():.2f}")
print(f"Avg SL Dist/ATR: {wins['sl_dist_atr'].mean():.2f}")

print("\n--- LOSSES ---")
losses = merged[merged['Reason'] == 'SL']
print(f"Count: {len(losses)}")
print(f"Avg ATR: {losses['atr'].mean():.2f}")
print(f"Avg RSI: {losses['rsi'].mean():.2f}")
print(f"Avg Body/ATR: {(losses['body'] / losses['atr']).mean():.2f}")
print(f"Avg Sweep/ATR: {(losses['sweep_depth'] / losses['atr']).mean():.2f}")
print(f"Avg Body/Range: {(losses['body'] / losses['range']).mean():.2f}")
print(f"Avg Dist EMA50/ATR: {losses['dist_ema50'].mean():.2f}")
print(f"Avg Sweep Wick Pct: {losses['sweep_wick_pct'].mean():.2f}")
print(f"Avg SL Dist/ATR: {losses['sl_dist_atr'].mean():.2f}")

print("\n--- ALL TRADES ---")
print(merged[['Time (BKK)', 'Type', 'Reason', 'body', 'atr', 'sl_dist_atr']].head(50))
mt5.shutdown()
