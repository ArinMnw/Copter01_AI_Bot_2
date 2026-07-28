import pandas as pd
import numpy as np

def find_last_mile():
    df = pd.read_csv('trades_365d_fast_features.csv')
    
    # Current safe traps
    s1 = (df['Type'] == 'SELL') & (df['rsi_7'] < 41.5) & (df['di_diff'] > 0.5)
    s2 = (df['Type'] == 'SELL') & (df['adx'] < 20.2) & (df['dist_ema50'] > -12.0)
    s3 = (df['Type'] == 'SELL') & (df['vol_ratio'] < 1.90) & (df['rsi'] < 39.0)
    s4 = (df['Type'] == 'SELL') & (df['z_score'] > 0.20) & (df['atr_pct'] < 0.31)
    s5 = (df['Type'] == 'SELL') & (df['rsi'] > 53.0) & (df['rsi_7'] < 37.0)
    b2 = (df['Type'] == 'BUY') & (df['vol_ratio'] < 0.55)
    
    current_mask = s1 | s2 | s3 | s4 | s5 | b2
    rem_df = df[~current_mask]
    
    rem_sell_sls = rem_df[(rem_df['Type']=='SELL') & (rem_df['Reason']=='SL')]
    all_sell_tps = df[(df['Type']=='SELL') & (df['Reason']=='TP')]
    
    print("Remaining SELL SLs to target:", len(rem_sell_sls))
    
    cols = ['rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'vol_ratio', 'dist_ema50', 'hour']
    for c1 in cols:
        for op1 in ['>', '<']:
            for v1 in np.percentile(rem_sell_sls[c1], np.linspace(10, 90, 15)):
                cond1 = (df['Type']=='SELL') & ((df[c1] > v1) if op1 == '>' else (df[c1] < v1))
                if len(all_sell_tps[cond1.loc[all_sell_tps.index]]) == 0:
                    sl_hits = len(rem_sell_sls[cond1.loc[rem_sell_sls.index]])
                    if sl_hits >= 2:
                        print(f"SELL 1-cond: {c1:10s} {op1} {v1:8.2f} | Drops extra SLs: {sl_hits}")
                for c2 in cols:
                    if c1 == c2: continue
                    for op2 in ['>', '<']:
                        for v2 in np.percentile(rem_sell_sls[c2], np.linspace(10, 90, 10)):
                            cond2 = (df['Type']=='SELL') & ((df[c2] > v2) if op2 == '>' else (df[c2] < v2))
                            cond = cond1 & cond2
                            if len(all_sell_tps[cond.loc[all_sell_tps.index]]) == 0:
                                sl_hits = len(rem_sell_sls[cond.loc[rem_sell_sls.index]])
                                if sl_hits >= 3:
                                    print(f"SELL 2-cond: {c1} {op1} {v1:.2f} AND {c2} {op2} {v2:.2f} | Drops extra SLs: {sl_hits}")

    # Now let's target the 3 BUY SLs (Trades 13, 21, 34) vs all 15 BUY TPs
    rem_buy_sls = rem_df[(rem_df['Type']=='BUY') & (rem_df['Reason']=='SL')]
    all_buy_tps = df[(df['Type']=='BUY') & (df['Reason']=='TP')]
    print("\nRemaining BUY SLs to target:", len(rem_buy_sls))
    for idx, row in rem_buy_sls.iterrows():
        print(f"Trade {idx} ({row['Time (BKK)']}): rsi={row['rsi']:.1f}, rsi7={row['rsi_7']:.1f}, adx={row['adx']:.1f}, di_diff={row['di_diff']:.1f}, z_score={row['z_score']:.2f}, atr_pct={row['atr_pct']:.2f}, vol_ratio={row['vol_ratio']:.2f}, dist_ema50={row['dist_ema50']:.1f}")

    for c1 in cols:
        for op1 in ['>', '<']:
            for v1 in np.percentile(rem_buy_sls[c1], [0, 25, 50, 75, 100]):
                cond1 = (df['Type']=='BUY') & ((df[c1] >= v1) if op1 == '>' else (df[c1] <= v1))
                if len(all_buy_tps[cond1.loc[all_buy_tps.index]]) == 0:
                    sl_hits = len(rem_buy_sls[cond1.loc[rem_buy_sls.index]])
                    if sl_hits >= 1:
                        print(f"BUY 1-cond: {c1:10s} {op1}= {v1:8.2f} | Drops extra BUY SLs: {sl_hits}")
                for c2 in cols:
                    if c1 == c2: continue
                    for op2 in ['>', '<']:
                        for v2 in np.percentile(rem_buy_sls[c2], [0, 50, 100]):
                            cond2 = (df['Type']=='BUY') & ((df[c2] >= v2) if op2 == '>' else (df[c2] <= v2))
                            cond = cond1 & cond2
                            if len(all_buy_tps[cond.loc[all_buy_tps.index]]) == 0:
                                sl_hits = len(rem_buy_sls[cond.loc[rem_buy_sls.index]])
                                if sl_hits >= 1:
                                    print(f"BUY 2-cond: {c1} {op1}= {v1:.2f} AND {c2} {op2}= {v2:.2f} | Drops extra BUY SLs: {sl_hits}")

if __name__ == '__main__':
    find_last_mile()
