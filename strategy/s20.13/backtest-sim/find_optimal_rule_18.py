import pandas as pd
import numpy as np

df = pd.read_csv('trade_features_17.csv')

sniper_times = ['2026-07-16 23:00', '2026-07-17 21:00', '2026-07-17 23:00']
sniper_df = df[df['time'].isin(sniper_times)]
print(f"Total trades: {len(df)}, Wins: {len(df[df['res']=='TP'])}, Losses: {len(df[df['res']=='SL'])}, BE: {len(df[df['res']=='BE'])}")

# Let's search for single or double condition rules that filter out SL trades without touching Sniper trades or TP trades
buy_df = df[df['type'] == 'BUY']
sell_df = df[df['type'] == 'SELL']

print("\n--- BUY TRADES (TP vs SL) ---")
print(f"BUY TP: {len(buy_df[buy_df['res']=='TP'])}, BUY SL: {len(buy_df[buy_df['res']=='SL'])}")

print("\n--- SELL TRADES (TP vs SL) ---")
print(f"SELL TP: {len(sell_df[sell_df['res']=='TP'])}, SELL SL: {len(sell_df[sell_df['res']=='SL'])}")

# Grid search for BUY filter
best_buy_rules = []
features = ['rsi', 'z_score', 'adx', 'atr', 'dist_ema20', 'dist_ema50', 'dist_ema200', 'body', 'wick_ratio', 'vol_ratio', 'macd_hist']

for f in features:
    # Try greater than threshold
    for val in np.percentile(buy_df[f], np.linspace(0, 100, 50)):
        # If we block when f > val
        remaining = buy_df[buy_df[f] <= val]
        snipers_rem = remaining[remaining['time'].isin(sniper_times)]
        if len(snipers_rem) == len(buy_df[buy_df['time'].isin(sniper_times)]): # keep all snipers
            tps = len(remaining[remaining['res'] == 'TP'])
            sls = len(remaining[remaining['res'] == 'SL'])
            orig_tps = len(buy_df[buy_df['res'] == 'TP'])
            orig_sls = len(buy_df[buy_df['res'] == 'SL'])
            if tps >= orig_tps - 1 and sls < orig_sls: # allowed to lose at most 1 TP if we drop SLs
                score = (orig_sls - sls) * 2 - (orig_tps - tps) * 3
                best_buy_rules.append({'rule': f"{f} > {val:.2f}", 'blocked_sl': orig_sls - sls, 'blocked_tp': orig_tps - tps, 'score': score})
    # Try less than threshold
    for val in np.percentile(buy_df[f], np.linspace(0, 100, 50)):
        remaining = buy_df[buy_df[f] >= val]
        snipers_rem = remaining[remaining['time'].isin(sniper_times)]
        if len(snipers_rem) == len(buy_df[buy_df['time'].isin(sniper_times)]):
            tps = len(remaining[remaining['res'] == 'TP'])
            sls = len(remaining[remaining['res'] == 'SL'])
            orig_tps = len(buy_df[buy_df['res'] == 'TP'])
            orig_sls = len(buy_df[buy_df['res'] == 'SL'])
            if tps >= orig_tps - 1 and sls < orig_sls:
                score = (orig_sls - sls) * 2 - (orig_tps - tps) * 3
                best_buy_rules.append({'rule': f"{f} < {val:.2f}", 'blocked_sl': orig_sls - sls, 'blocked_tp': orig_tps - tps, 'score': score})

best_buy_rules.sort(key=lambda x: x['score'], reverse=True)
print("\nTop 10 BUY rules:")
for r in best_buy_rules[:10]:
    print(r)

# Grid search for SELL filter
best_sell_rules = []
for f in features:
    for val in np.percentile(sell_df[f], np.linspace(0, 100, 50)):
        remaining = sell_df[sell_df[f] <= val]
        snipers_rem = remaining[remaining['time'].isin(sniper_times)]
        if len(snipers_rem) == len(sell_df[sell_df['time'].isin(sniper_times)]):
            tps = len(remaining[remaining['res'] == 'TP'])
            sls = len(remaining[remaining['res'] == 'SL'])
            orig_tps = len(sell_df[sell_df['res'] == 'TP'])
            orig_sls = len(sell_df[sell_df['res'] == 'SL'])
            if tps >= orig_tps - 1 and sls < orig_sls:
                score = (orig_sls - sls) * 2 - (orig_tps - tps) * 3
                best_sell_rules.append({'rule': f"{f} > {val:.2f}", 'blocked_sl': orig_sls - sls, 'blocked_tp': orig_tps - tps, 'score': score})
    for val in np.percentile(sell_df[f], np.linspace(0, 100, 50)):
        remaining = sell_df[sell_df[f] >= val]
        snipers_rem = remaining[remaining['time'].isin(sniper_times)]
        if len(snipers_rem) == len(sell_df[sell_df['time'].isin(sniper_times)]):
            tps = len(remaining[remaining['res'] == 'TP'])
            sls = len(remaining[remaining['res'] == 'SL'])
            orig_tps = len(sell_df[sell_df['res'] == 'TP'])
            orig_sls = len(sell_df[sell_df['res'] == 'SL'])
            if tps >= orig_tps - 1 and sls < orig_sls:
                score = (orig_sls - sls) * 2 - (orig_tps - tps) * 3
                best_sell_rules.append({'rule': f"{f} < {val:.2f}", 'blocked_sl': orig_sls - sls, 'blocked_tp': orig_tps - tps, 'score': score})

best_sell_rules.sort(key=lambda x: x['score'], reverse=True)
print("\nTop 10 SELL rules:")
for r in best_sell_rules[:10]:
    print(r)
