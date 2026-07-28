import pandas as pd
import numpy as np

def run_targeted_search():
    df = pd.read_csv('trades_365d_fast_features.csv')
    print("Total trades:", len(df))
    
    # Let's check BUY rules first
    buy_df = df[df['Type'] == 'BUY']
    buy_tps = buy_df[buy_df['Reason'] == 'TP']
    buy_sls = buy_df[buy_df['Reason'] == 'SL']
    
    print("\n==================== BUY FILTERS (Targeting 4 SLs) ====================")
    cols = ['rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'body_pct', 'vol_ratio', 'dist_ema50', 'hour']
    for c1 in cols:
        for op1 in ['>', '<']:
            for v1 in np.percentile(buy_df[c1], np.linspace(10, 90, 20)):
                cond1 = (buy_df[c1] > v1) if op1 == '>' else (buy_df[c1] < v1)
                if len(buy_tps[cond1.loc[buy_tps.index]]) == 0:
                    sl_hits = len(buy_sls[cond1.loc[buy_sls.index]])
                    if sl_hits >= 1:
                        print(f"BUY 1-cond: {c1:10s} {op1} {v1:8.2f} | Drops BUY SLs: {sl_hits:2d}")
                for c2 in cols:
                    if c1 == c2: continue
                    for op2 in ['>', '<']:
                        for v2 in np.percentile(buy_df[c2], np.linspace(10, 90, 10)):
                            cond2 = (buy_df[c2] > v2) if op2 == '>' else (buy_df[c2] < v2)
                            cond = cond1 & cond2
                            if len(buy_tps[cond.loc[buy_tps.index]]) == 0:
                                sl_hits = len(buy_sls[cond.loc[buy_sls.index]])
                                if sl_hits >= 2:
                                    print(f"BUY 2-cond: {c1} {op1} {v1:.2f} AND {c2} {op2} {v2:.2f} | Drops BUY SLs: {sl_hits}")

    # Now let's check SELL filters targeting ALL 31 SELL SLs
    sell_df = df[df['Type'] == 'SELL']
    sell_tps = sell_df[sell_df['Reason'] == 'TP']
    sell_sls = sell_df[sell_df['Reason'] == 'SL']
    
    print("\n==================== SELL FILTERS (Targeting 31 SLs) ====================")
    sell_rules_found = []
    for c1 in cols:
        for op1 in ['>', '<']:
            for v1 in np.percentile(sell_df[c1], np.linspace(5, 95, 20)):
                cond1 = (sell_df[c1] > v1) if op1 == '>' else (sell_df[c1] < v1)
                if len(sell_tps[cond1.loc[sell_tps.index]]) == 0:
                    sl_hits = len(sell_sls[cond1.loc[sell_sls.index]])
                    if sl_hits >= 4:
                        sell_rules_found.append((f"SELL 1-cond: {c1} {op1} {v1:.2f}", sl_hits, cond1))
                for c2 in cols:
                    if c1 == c2: continue
                    for op2 in ['>', '<']:
                        for v2 in np.percentile(sell_df[c2], np.linspace(10, 90, 10)):
                            cond2 = (sell_df[c2] > v2) if op2 == '>' else (sell_df[c2] < v2)
                            cond = cond1 & cond2
                            if len(sell_tps[cond.loc[sell_tps.index]]) == 0:
                                sl_hits = len(sell_sls[cond.loc[sell_sls.index]])
                                if sl_hits >= 6:
                                    sell_rules_found.append((f"SELL 2-cond: {c1} {op1} {v1:.2f} AND {c2} {op2} {v2:.2f}", sl_hits, cond))
                                    
    sell_rules_found.sort(key=lambda x: x[1], reverse=True)
    seen = set()
    for desc, hits, cond in sell_rules_found[:30]:
        if desc[:20] in seen: continue
        seen.add(desc[:20])
        print(f"  {desc:60s} | Drops SELL SLs: {hits}")

if __name__ == '__main__':
    run_targeted_search()
