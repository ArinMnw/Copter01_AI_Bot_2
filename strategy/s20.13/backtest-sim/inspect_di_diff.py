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
df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
df['wick_ratio'] = (df['upper_wick'] + df['lower_wick']) / (df['body'] + 0.0001)

df_trades = pd.read_csv('s20_13_18_trades.csv')
sells = df_trades[df_trades['Type']=='SELL']
merged = pd.merge(sells, df, left_on='Time (BKK)', right_on='time_str', how='inner')
tps = merged[merged['Reason']=='TP']
sls = merged[merged['Reason']=='SL']

features = ['rsi', 'rsi_7', 'adx', 'di_diff', 'body_pct', 'vol_ratio', 'dist_ema50', 'z_score', 'atr_pct', 'wick_ratio']
print('=== 1-Feature & 2-Feature Rules dropping each SL with 0 TP drop ===')
for sl_idx, sl_row in sls.iterrows():
    print(f"\n--- SL {sl_row['time_str']} ---")
    matched_rules = []
    # 1-feature
    for f in features:
        val = sl_row[f]
        for op in ['>=', '<=']:
            c = (merged[f] >= val - 1e-6) if op == '>=' else (merged[f] <= val + 1e-6)
            if (c & (merged['Reason']=='TP')).sum() == 0 and c.loc[sl_idx]:
                matched_rules.append(f"{f} {op} {val:.3f}")
    # 2-feature
    for i, f1 in enumerate(features):
        val1 = sl_row[f1]
        for op1 in ['>=', '<=']:
            c1 = (merged[f1] >= val1 - 1e-6) if op1 == '>=' else (merged[f1] <= val1 + 1e-6)
            for j, f2 in enumerate(features):
                if i >= j: continue
                val2 = sl_row[f2]
                for op2 in ['>=', '<=']:
                    c2 = (merged[f2] >= val2 - 1e-6) if op2 == '>=' else (merged[f2] <= val2 + 1e-6)
                    c = c1 & c2
                    if (c & (merged['Reason']=='TP')).sum() == 0 and c.loc[sl_idx]:
                        matched_rules.append(f"{f1} {op1} {val1:.3f} and {f2} {op2} {val2:.3f}")
    for r in matched_rules[:10]:
        print("  ", r)
