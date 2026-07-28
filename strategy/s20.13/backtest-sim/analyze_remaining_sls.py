import pandas as pd
import numpy as np

def run_deep_check():
    df = pd.read_csv('trades_365d_fast_features.csv')
    
    # Check SELL: dist_ema50 > 0 and di_diff > 0
    sell_test = (df['Type'] == 'SELL') & (df['dist_ema50'] > 0) & (df['di_diff'] > 0)
    print("SELL dist_ema50 > 0 and di_diff > 0 -> TP hit:", len(df[sell_test & (df['Reason']=='TP')]), "SL hit:", len(df[sell_test & (df['Reason']=='SL')]))
    
    # What if we add a threshold like di_diff > 0 and dist_ema50 > 15?
    for ema_val in [0, 5, 10, 15, 20, 25]:
        for di_val in [-5, 0, 2, 5]:
            st = (df['Type'] == 'SELL') & (df['dist_ema50'] > ema_val) & (df['di_diff'] > di_val)
            tp_hit = len(df[st & (df['Reason']=='TP')])
            sl_hit = len(df[st & (df['Reason']=='SL')])
            if tp_hit == 0 and sl_hit > 0:
                print(f"[PASS] SELL dist_ema50 > {ema_val:2d} and di_diff > {di_val:2d} | SL hit: {sl_hit}")
                
    # Now let's inspect the 4 BUY SLs and compare directly against all 15 BUY TPs
    buy_tps = df[(df['Type']=='BUY') & (df['Reason']=='TP')]
    buy_sls = df[(df['Type']=='BUY') & (df['Reason']=='SL')]
    
    print("\n--- BUY TPs vs BUY SLs ---")
    for idx, sl_row in buy_sls.iterrows():
        print(f"\nBUY SL Trade {idx} ({sl_row['Time (BKK)']}): rsi={sl_row['rsi']:.1f}, rsi7={sl_row['rsi_7']:.1f}, adx={sl_row['adx']:.1f}, di_diff={sl_row['di_diff']:.1f}, z_score={sl_row['z_score']:.2f}, atr_pct={sl_row['atr_pct']:.2f}, vol_ratio={sl_row['vol_ratio']:.2f}, dist_ema50={sl_row['dist_ema50']:.1f}")
        
    # Find features where ALL 15 BUY TPs are DIFFERENT from at least 1 BUY SL
    print("\nSearching for 0-TP BUY rules...")
    cols = ['rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'body_pct', 'vol_ratio', 'dist_ema50', 'hour']
    for c1 in cols:
        for op1 in ['>', '<']:
            for v1 in np.percentile(buy_sls[c1], [0, 25, 50, 75, 100]):
                cond1 = (df['Type']=='BUY') & ((df[c1] >= v1) if op1 == '>' else (df[c1] <= v1))
                if len(df[cond1 & (df['Reason']=='TP')]) == 0 and len(df[cond1 & (df['Reason']=='SL')]) > 0:
                    print(f"[PASS] BUY 1-cond: {c1} {op1}= {v1:.2f} | Drops BUY SLs: {len(df[cond1 & (df['Reason']=='SL')])}")
                for c2 in cols:
                    if c1 == c2: continue
                    for op2 in ['>', '<']:
                        for v2 in np.percentile(buy_sls[c2], [0, 25, 50, 75, 100]):
                            cond2 = (df[c2] >= v2) if op2 == '>' else (df[c2] <= v2)
                            cond = cond1 & cond2
                            if len(df[cond & (df['Reason']=='TP')]) == 0 and len(df[cond & (df['Reason']=='SL')]) > 0:
                                print(f"[PASS] BUY 2-cond: {c1} {op1}= {v1:.2f} AND {c2} {op2}= {v2:.2f} | Drops BUY SLs: {len(df[cond & (df['Reason']=='SL')])}")

if __name__ == '__main__':
    run_deep_check()
