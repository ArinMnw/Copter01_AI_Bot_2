import pandas as pd
import numpy as np

def search_all_rules():
    df = pd.read_csv('trades_365d_fast_features.csv')
    
    for side in ['BUY', 'SELL']:
        print(f"\n==================== SEARCHING {side} RULES ====================")
        sub = df[df['Type'] == side]
        tps = sub[sub['Reason'] == 'TP']
        sls = sub[sub['Reason'] == 'SL']
        
        cols = ['rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'body_pct', 'vol_ratio', 'dist_ema50', 'dist_ema200', 'hour']
        
        candidates = []
        for c1 in cols:
            for op1 in ['>', '<']:
                vals = np.percentile(sub[c1], np.linspace(5, 95, 30))
                for v1 in vals:
                    cond1 = (sub[c1] > v1) if op1 == '>' else (sub[c1] < v1)
                    tp_hit = len(tps[cond1.loc[tps.index]])
                    sl_hit = len(sls[cond1.loc[sls.index]])
                    if tp_hit == 0 and sl_hit >= (2 if side == 'BUY' else 3):
                        candidates.append((f"{c1} {op1} {v1:.2f}", sl_hit, cond1))
                        
                    # 2-condition rules
                    for c2 in cols:
                        if c1 == c2: continue
                        for op2 in ['>', '<']:
                            vals2 = np.percentile(sub[c2], np.linspace(10, 90, 15))
                            for v2 in vals2:
                                cond2 = (sub[c2] > v2) if op2 == '>' else (sub[c2] < v2)
                                cond = cond1 & cond2
                                tp_hit = len(tps[cond.loc[tps.index]])
                                sl_hit = len(sls[cond.loc[sls.index]])
                                if tp_hit == 0 and sl_hit >= (2 if side == 'BUY' else 5):
                                    candidates.append((f"{c1} {op1} {v1:.2f} AND {c2} {op2} {v2:.2f}", sl_hit, cond))

        candidates.sort(key=lambda x: x[1], reverse=True)
        # deduplicate by sl_hit and string similarity
        seen = set()
        print(f"Top candidate rules for {side} (0 TP hit):")
        for desc, sl_hit, cond in candidates[:30]:
            if desc[:15] in seen: continue
            seen.add(desc[:15])
            print(f"  {desc:55s} | Drops SL: {sl_hit}")
            
if __name__ == '__main__':
    search_all_rules()
