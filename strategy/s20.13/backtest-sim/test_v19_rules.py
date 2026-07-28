import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
mt5.initialize(path=path)
symbol = 'XAUUSD.iux'
end = datetime.now()
start = end - timedelta(days=150)
rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start, end)
mt5.shutdown()

df_rates = pd.DataFrame(rates)
df_rates['time_dt'] = pd.to_datetime(df_rates['time'], unit='s')
df_rates['time_bkk'] = df_rates['time_dt'] + timedelta(hours=7)
df_rates['time_str'] = df_rates['time_bkk'].dt.strftime('%Y-%m-%d %H:%M')

df = df_rates.copy()
delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df['rsi'] = 100 - (100 / (1 + (gain / loss)))

gain7 = (delta.where(delta > 0, 0)).rolling(7).mean()
loss7 = (-delta.where(delta < 0, 0)).rolling(7).mean()
df['rsi_7'] = 100 - (100 / (1 + (gain7 / loss7)))

sma20 = df['close'].rolling(20).mean()
std20 = df['close'].rolling(20).std()
df['z_score'] = (df['close'] - sma20) / std20

tr1 = pd.DataFrame(df['high'] - df['low'])
tr2 = pd.DataFrame(abs(df['high'] - df['close'].shift(1)))
tr3 = pd.DataFrame(abs(df['low'] - df['close'].shift(1)))
tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
atr14 = tr.rolling(14).mean()
df['atr_pct'] = (atr14 / df['close']) * 100

plus_dm = df['high'].diff()
minus_dm = df['low'].shift() - df['low']
plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
tr14 = tr.rolling(14).sum()
plus_di14 = 100 * (pd.Series(plus_dm).rolling(14).sum() / tr14)
minus_di14 = 100 * (pd.Series(minus_dm).rolling(14).sum() / tr14)
dx = 100 * (np.abs(plus_di14 - minus_di14) / (plus_di14 + minus_di14))
df['adx'] = dx.rolling(14).mean()
df['di_diff'] = plus_di14 - minus_di14

df['range'] = df['high'] - df['low']
df['body'] = abs(df['close'] - df['open'])
df['body_pct'] = df['body'] / (df['range'] + 0.0001)
df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1.0)
df['dist_ema50'] = df['close'] - df['close'].ewm(span=50, adjust=False).mean()

df_trades = pd.read_csv('s20_13_18_trades.csv')
sells = df_trades[df_trades['Type']=='SELL']
merged = pd.merge(sells, df, left_on='Time (BKK)', right_on='time_str', how='inner')

# Test v19 SELL Filter exclusions
def is_blocked_sell_v19(row):
    # Rule A: Extreme Doji indecision (body < 14.5% of range)
    if row['body_pct'] < 0.145:
        return True, "Extreme Doji"
    # Rule B: Weak Momentum Oversold Trap (RSI near 36 without deep Bollinger z_score breakout)
    if row['rsi'] < 37.0 and row['z_score'] > -1.80:
        return True, "Oversold Trap"
    # Rule C: Low Volume / Low ADX Chop (ADX < 17 and volume below 90% of MA20)
    if row['adx'] < 17.5 and row['vol_ratio'] < 0.90:
        return True, "Low Vol Chop"
    # Rule D: RSI Divergence Trap (RSI14 > 58.5 while RSI7 < 41.5)
    if row['rsi'] > 58.5 and row['rsi_7'] < 41.5:
        return True, "RSI Div Trap"
    return False, ""

print("=== Testing v19 exclusions on v18 SELL trades ===")
tp_dropped = 0
sl_dropped = 0

for idx, r in merged.iterrows():
    blocked, reason = is_blocked_sell_v19(r)
    if blocked:
        print(f"BLOCKED [{reason}]: {r['time_str']} ({r['Reason']})")
        if r['Reason'] == 'TP': tp_dropped += 1
        elif r['Reason'] == 'SL': sl_dropped += 1

print(f"\nSummary: Dropped {sl_dropped}/4 SLs, Dropped {tp_dropped}/36 TPs!")
