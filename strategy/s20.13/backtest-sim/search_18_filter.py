import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from strategy20_13_17 import strategy_20_13_17

path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
if not mt5.initialize(path=path):
    print("MT5 initialize failed")
    sys.exit(1)

symbol = "XAUUSD.iux"
end = datetime.now()
start = end - timedelta(days=150)
rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start, end)
mt5.shutdown()

if rates is None or len(rates) == 0:
    print("No rates fetched")
    sys.exit(1)

df_rates = pd.DataFrame(rates)
df_rates['time_dt'] = pd.to_datetime(df_rates['time'], unit='s')
# BKK time is UTC+7
df_rates['time_bkk'] = df_rates['time_dt'] + timedelta(hours=7)

# Calculate extensive features on df_rates
df = df_rates.copy()
# RSI
delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
rs = gain / loss
df['rsi'] = 100 - (100 / (1 + rs))

# Z-Score
sma20 = df['close'].rolling(20).mean()
std20 = df['close'].rolling(20).std()
df['z_score'] = (df['close'] - sma20) / std20

# ADX
plus_dm = df['high'].diff()
minus_dm = df['low'].shift() - df['low']
plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
tr1 = pd.DataFrame(df['high'] - df['low'])
tr2 = pd.DataFrame(abs(df['high'] - df['close'].shift(1)))
tr3 = pd.DataFrame(abs(df['low'] - df['close'].shift(1)))
frames = [tr1, tr2, tr3]
tr = pd.concat(frames, axis=1, join='inner').max(axis=1)
atr14 = tr.rolling(14).mean()
plus_di = 100 * (pd.Series(plus_dm).rolling(14).mean() / atr14)
minus_di = 100 * (pd.Series(minus_dm).rolling(14).mean() / atr14)
dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
df['adx'] = dx.rolling(14).mean()
df['atr'] = atr14
df['atr_pct'] = (df['atr'] / df['close']) * 100

# EMAs
df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
df['dist_ema20'] = df['close'] - df['ema20']
df['dist_ema50'] = df['close'] - df['ema50']
df['dist_ema200'] = df['close'] - df['ema200']

# Candle anatomy
df['body'] = abs(df['close'] - df['open'])
df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
df['wick_ratio'] = (df['upper_wick'] + df['lower_wick']) / (df['body'] + 0.0001)

# Volume
df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1)

# MACD
exp1 = df['close'].ewm(span=12, adjust=False).mean()
exp2 = df['close'].ewm(span=26, adjust=False).mean()
df['macd'] = exp1 - exp2
df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
df['macd_hist'] = df['macd'] - df['macd_signal']

# We need to load s20_13_17_trades.csv to know exact trade times and results
df_trades = pd.read_csv('s20_13_17_trades.csv')
print(f"Loaded {len(df_trades)} trades from s20_13_17_trades.csv")

# Match each trade with its features at entry time
trade_features = []
for idx, row in df_trades.iterrows():
    t_str = str(row['Time (BKK)']) # format e.g. 2026-03-04 21:00
    # Match with df['time_bkk'] formatted to string
    match = df[df['time_bkk'].dt.strftime('%Y-%m-%d %H:%M') == t_str]
    if len(match) > 0:
        bar = match.iloc[0]
        trade_features.append({
            'time': t_str,
            'type': row['Type'],
            'res': row['Reason'],
            'pnl': row['P&L'],
            'rsi': bar['rsi'],
            'z_score': bar['z_score'],
            'adx': bar['adx'],
            'atr': bar['atr'],
            'atr_pct': bar['atr_pct'],
            'dist_ema20': bar['dist_ema20'],
            'dist_ema50': bar['dist_ema50'],
            'dist_ema200': bar['dist_ema200'],
            'body': bar['body'],
            'upper_wick': bar['upper_wick'],
            'lower_wick': bar['lower_wick'],
            'wick_ratio': bar['wick_ratio'],
            'vol_ratio': bar['vol_ratio'],
            'macd_hist': bar['macd_hist'],
            'hour': bar['time_bkk'].hour
        })
    else:
        print(f"Could not match time: {t_str}")

tf_df = pd.DataFrame(trade_features)
print(f"Matched {len(tf_df)} trades with features.")

# Check Sniper timestamps
sniper_times = ['2026-07-16 23:00', '2026-07-17 21:00', '2026-07-17 23:00']
print("\n--- SNIPER TRADES FEATURES ---")
print(tf_df[tf_df['time'].isin(sniper_times)][['time', 'type', 'res', 'rsi', 'z_score', 'adx', 'dist_ema50', 'vol_ratio', 'wick_ratio']])

print("\n--- COMPARISON OF MEANS (WINS vs LOSSES) ---")
wins_df = tf_df[tf_df['res'] == 'TP']
loss_df = tf_df[tf_df['res'] == 'SL']

for col in ['rsi', 'z_score', 'adx', 'atr', 'dist_ema50', 'dist_ema200', 'body', 'wick_ratio', 'vol_ratio', 'macd_hist']:
    print(f"{col:15s} | Win mean: {wins_df[col].mean():8.2f} | Loss mean: {loss_df[col].mean():8.2f} | Min Win: {wins_df[col].min():8.2f} | Max Win: {wins_df[col].max():8.2f} | Min Loss: {loss_df[col].min():8.2f} | Max Loss: {loss_df[col].max():8.2f}")

# Save to csv for deep inspection
tf_df.to_csv('trade_features_17.csv', index=False)
print("\nSaved trade_features_17.csv")
