import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
mt5.initialize(path=path)
symbol = "XAUUSD.iux"
end = datetime.now()
start = end - timedelta(days=150)
rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start, end)
mt5.shutdown()

df_rates = pd.DataFrame(rates)
df_rates['time_dt'] = pd.to_datetime(df_rates['time'], unit='s')
df_rates['time_bkk'] = df_rates['time_dt'] + timedelta(hours=7)

df = df_rates.copy()
# RSIs
for n in [7, 14, 21]:
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(n).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(n).mean()
    rs = gain / loss
    df[f'rsi_{n}'] = 100 - (100 / (1 + rs))

# Z-Scores
for n in [10, 20, 50]:
    sma = df['close'].rolling(n).mean()
    std = df['close'].rolling(n).std()
    df[f'z_score_{n}'] = (df['close'] - sma) / std

# ADX
plus_dm = df['high'].diff()
minus_dm = df['low'].shift() - df['low']
plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
tr1 = pd.DataFrame(df['high'] - df['low'])
tr2 = pd.DataFrame(abs(df['high'] - df['close'].shift(1)))
tr3 = pd.DataFrame(abs(df['low'] - df['close'].shift(1)))
tr = pd.concat([tr1, tr2, tr3], axis=1, join='inner').max(axis=1)
atr14 = tr.rolling(14).mean()
plus_di = 100 * (pd.Series(plus_dm).rolling(14).mean() / atr14)
minus_di = 100 * (pd.Series(minus_dm).rolling(14).mean() / atr14)
dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
df['adx'] = dx.rolling(14).mean()
df['plus_di'] = plus_di
df['minus_di'] = minus_di
df['di_diff'] = plus_di - minus_di
df['atr'] = atr14

# EMAs & SMA
df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
df['ema100'] = df['close'].ewm(span=100, adjust=False).mean()
df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
df['dist_ema20'] = df['close'] - df['ema20']
df['dist_ema50'] = df['close'] - df['ema50']
df['dist_ema100'] = df['close'] - df['ema100']
df['dist_ema200'] = df['close'] - df['ema200']

# Candle anatomy
df['body'] = abs(df['close'] - df['open'])
df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
df['wick_ratio'] = (df['upper_wick'] + df['lower_wick']) / (df['body'] + 0.0001)
df['range'] = df['high'] - df['low']
df['body_pct'] = df['body'] / (df['range'] + 0.0001)
df['prev_body'] = df['body'].shift(1)
df['prev_range'] = df['range'].shift(1)

# Momentum
df['mom_1'] = df['close'] - df['close'].shift(1)
df['mom_3'] = df['close'] - df['close'].shift(3)
df['mom_5'] = df['close'] - df['close'].shift(5)

# Load trades from trade_features_17.csv
df_trades = pd.read_csv('trade_features_17.csv')

# Merge all new features
all_features = []
for idx, row in df_trades.iterrows():
    t_str = str(row['time'])
    match = df[df['time_bkk'].dt.strftime('%Y-%m-%d %H:%M') == t_str]
    if len(match) > 0:
        bar = match.iloc[0]
        d_item = row.to_dict()
        for c in ['rsi_7', 'rsi_21', 'z_score_10', 'z_score_50', 'plus_di', 'minus_di', 'di_diff', 'dist_ema100', 'body_pct', 'prev_body', 'prev_range', 'mom_1', 'mom_3', 'mom_5']:
            d_item[c] = bar[c]
        all_features.append(d_item)

tf_df = pd.DataFrame(all_features)
print(f"Extracted {len(tf_df)} trades with deep features.")

# Save
tf_df.to_csv('trade_features_18_deep.csv', index=False)

# Now let's do combinatorial rule search (pairs of features) for BUY and SELL
sniper_times = ['2026-07-16 23:00', '2026-07-17 21:00', '2026-07-17 23:00']
buy_df = tf_df[tf_df['type'] == 'BUY']
sell_df = tf_df[tf_df['type'] == 'SELL']

feature_cols = [c for c in tf_df.columns if c not in ['time', 'type', 'res', 'pnl']]

print("\n=== SEARCHING BUY PAIR RULES ===")
best_buy = []
for i, f1 in enumerate(feature_cols):
    for f2 in feature_cols[i+1:]:
        # Try (f1 > v1 and f2 > v2), (f1 > v1 and f2 < v2), etc.
        for op1 in ['>', '<']:
            for op2 in ['>', '<']:
                for q1 in [20, 50, 70, 80, 90]:
                    v1 = np.percentile(buy_df[f1], q1)
                    cond1 = (buy_df[f1] > v1) if op1 == '>' else (buy_df[f1] < v1)
                    for q2 in [20, 50, 70, 80, 90]:
                        v2 = np.percentile(buy_df[f2], q2)
                        cond2 = (buy_df[f2] > v2) if op2 == '>' else (buy_df[f2] < v2)
                        
                        cond = cond1 & cond2
                        rem = buy_df[~cond] # remaining after blocking when cond is true
                        
                        # Check sniper
                        if len(rem[rem['time'].isin(sniper_times)]) == len(buy_df[buy_df['time'].isin(sniper_times)]):
                            tps = len(rem[rem['res'] == 'TP'])
                            sls = len(rem[rem['res'] == 'SL'])
                            orig_tps = len(buy_df[buy_df['res'] == 'TP'])
                            orig_sls = len(buy_df[buy_df['res'] == 'SL'])
                            
                            if tps >= orig_tps - 1 and sls < orig_sls - 1: # remove at least 2 SLs, at most 1 TP
                                score = (orig_sls - sls) * 3 - (orig_tps - tps) * 4
                                best_buy.append({
                                    'rule': f"({f1} {op1} {v1:.2f}) and ({f2} {op2} {v2:.2f})",
                                    'drop_sl': orig_sls - sls,
                                    'drop_tp': orig_tps - tps,
                                    'score': score
                                })

best_buy.sort(key=lambda x: x['score'], reverse=True)
for r in best_buy[:10]:
    print(r)

print("\n=== SEARCHING SELL PAIR RULES ===")
best_sell = []
for i, f1 in enumerate(feature_cols):
    for f2 in feature_cols[i+1:]:
        for op1 in ['>', '<']:
            for op2 in ['>', '<']:
                for q1 in [20, 50, 70, 80, 90]:
                    v1 = np.percentile(sell_df[f1], q1)
                    cond1 = (sell_df[f1] > v1) if op1 == '>' else (sell_df[f1] < v1)
                    for q2 in [20, 50, 70, 80, 90]:
                        v2 = np.percentile(sell_df[f2], q2)
                        cond2 = (sell_df[f2] > v2) if op2 == '>' else (sell_df[f2] < v2)
                        
                        cond = cond1 & cond2
                        rem = sell_df[~cond]
                        
                        if len(rem[rem['time'].isin(sniper_times)]) == len(sell_df[sell_df['time'].isin(sniper_times)]):
                            tps = len(rem[rem['res'] == 'TP'])
                            sls = len(rem[rem['res'] == 'SL'])
                            orig_tps = len(sell_df[sell_df['res'] == 'TP'])
                            orig_sls = len(sell_df[sell_df['res'] == 'SL'])
                            
                            if tps >= orig_tps - 1 and sls < orig_sls - 1:
                                score = (orig_sls - sls) * 3 - (orig_tps - tps) * 4
                                best_sell.append({
                                    'rule': f"({f1} {op1} {v1:.2f}) and ({f2} {op2} {v2:.2f})",
                                    'drop_sl': orig_sls - sls,
                                    'drop_tp': orig_tps - tps,
                                    'score': score
                                })

best_sell.sort(key=lambda x: x['score'], reverse=True)
for r in best_sell[:10]:
    print(r)
