import pandas as pd
import numpy as np

def test_rules():
    df = pd.read_csv('trades_365d_fast_features.csv')
    print("Total initial:", len(df), "| TP:", len(df[df['Reason']=='TP']), "| SL:", len(df[df['Reason']=='SL']), "| BE:", len(df[df['Reason']=='BE']))
    
    # Separate BUY and SELL
    buy_df = df[df['Type'] == 'BUY'].copy()
    sell_df = df[df['Type'] == 'SELL'].copy()
    
    print("\n--- BUY TRADES BEFORE ---")
    print("TP:", len(buy_df[buy_df['Reason']=='TP']), "SL:", len(buy_df[buy_df['Reason']=='SL']))
    
    # Let's inspect the 4 BUY SLs
    buy_sls = buy_df[buy_df['Reason']=='SL']
    print("\nBUY SLs:")
    print(buy_sls[['Time (BKK)', 'rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'body_pct', 'vol_ratio', 'dist_ema50', 'hour']].to_string())
    
    print("\n--- SELL TRADES BEFORE ---")
    print("TP:", len(sell_df[sell_df['Reason']=='TP']), "SL:", len(sell_df[sell_df['Reason']=='SL']))
    
    # Let's check candidate SELL filters
    # We want filters that hit SELL SLs but 0 SELL TPs
    sell_tps = sell_df[sell_df['Reason']=='TP']
    sell_sls = sell_df[sell_df['Reason']=='SL']
    
    print("\nTesting candidate SELL rules...")
    # 1. High RSI + negative di_diff / low adx
    # Let's see feature correlations
    for col in ['rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'body_pct', 'vol_ratio', 'dist_ema50', 'hour']:
        tp_mean = sell_tps[col].mean()
        sl_mean = sell_sls[col].mean()
        print(f"{col:12s} | TP Mean: {tp_mean:8.2f} | SL Mean: {sl_mean:8.2f} | Diff: {sl_mean - tp_mean:8.2f}")
        
    # Let's search for decision tree or threshold blocks that drop > 0 SL and 0 TP
    good_rules = []
    # Test simple 2-condition rules
    cols = ['rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'body_pct', 'vol_ratio', 'dist_ema50']
    
    for c1 in cols:
        for op1 in ['>', '<']:
            for val1 in np.percentile(sell_df[c1], [10, 20, 30, 40, 50, 60, 70, 80, 90]):
                cond1 = (sell_df[c1] > val1) if op1 == '>' else (sell_df[c1] < val1)
                sl_hit = len(sell_sls[cond1.loc[sell_sls.index]])
                tp_hit = len(sell_tps[cond1.loc[sell_tps.index]])
                if tp_hit == 0 and sl_hit >= 3:
                    good_rules.append((f"SELL: {c1} {op1} {val1:.2f}", sl_hit, tp_hit))
                
                for c2 in cols:
                    if c1 == c2: continue
                    for op2 in ['>', '<']:
                        for val2 in np.percentile(sell_df[c2], [15, 30, 50, 70, 85]):
                            cond2 = (sell_df[c2] > val2) if op2 == '>' else (sell_df[c2] < val2)
                            cond = cond1 & cond2
                            sl_hit = len(sell_sls[cond.loc[sell_sls.index]])
                            tp_hit = len(sell_tps[cond.loc[sell_tps.index]])
                            if tp_hit == 0 and sl_hit >= 4:
                                good_rules.append((f"SELL: {c1} {op1} {val1:.2f} AND {c2} {op2} {val2:.2f}", sl_hit, tp_hit))

    print(f"\nFound {len(good_rules)} candidate rules with 0 TP hit:")
    # sort by sl_hit desc
    good_rules.sort(key=lambda x: x[1], reverse=True)
    for r in good_rules[:30]:
        print(f"  {r[0]:50s} | SL dropped: {r[1]} | TP dropped: {r[2]}")

if __name__ == '__main__':
    test_rules()
