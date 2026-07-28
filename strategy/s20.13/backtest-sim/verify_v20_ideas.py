import pandas as pd
import numpy as np

def test_ideas():
    df = pd.read_csv('trades_365d_fast_features.csv')
    print("Initial -> TP:", len(df[df['Reason']=='TP']), "SL:", len(df[df['Reason']=='SL']), "BE:", len(df[df['Reason']=='BE']))
    
    # Check BUY traps
    buy_tps = df[(df['Type']=='BUY') & (df['Reason']=='TP')]
    buy_sls = df[(df['Type']=='BUY') & (df['Reason']=='SL')]
    print("\n--- BUY TRAPS ---")
    
    # Candidate 1: Low volume in downtrend
    b1 = (df['Type'] == 'BUY') & (df['vol_ratio'] < 0.75) & (df['di_diff'] < 0)
    print("B1 -> Hits TP:", len(df[b1 & (df['Reason']=='TP')]), "Hits SL:", len(df[b1 & (df['Reason']=='SL')]))
    
    # Candidate 2: High ATR% chop with moderate RSI
    b2 = (df['Type'] == 'BUY') & (df['atr_pct'] > 0.55) & (df['rsi'] < 48.0)
    print("B2 -> Hits TP:", len(df[b2 & (df['Reason']=='TP')]), "Hits SL:", len(df[b2 & (df['Reason']=='SL')]))

    # Candidate 3: dist_ema50 between -30 and -20 in downtrend
    b3 = (df['Type'] == 'BUY') & (df['dist_ema50'] < -20.0) & (df['dist_ema50'] > -35.0) & (df['di_diff'] < -5.0)
    print("B3 -> Hits TP:", len(df[b3 & (df['Reason']=='TP')]), "Hits SL:", len(df[b3 & (df['Reason']=='SL')]))
    
    # Check SELL traps
    print("\n--- SELL TRAPS ---")
    s1 = (df['Type'] == 'SELL') & (df['rsi_7'] < 41.5) & (df['di_diff'] > -1.0)
    s2 = (df['Type'] == 'SELL') & (df['adx'] < 20.5) & (df['dist_ema50'] > -12.5)
    s3 = (df['Type'] == 'SELL') & (df['vol_ratio'] < 1.95) & (df['rsi'] < 39.5)
    s4 = (df['Type'] == 'SELL') & (df['z_score'] > 0.20) & (df['atr_pct'] < 0.31)
    s5 = (df['Type'] == 'SELL') & (df['dist_ema50'] > 17.0) & (df['rsi_7'] < 55.0)
    s6 = (df['Type'] == 'SELL') & (df['di_diff'] > 2.5) & (df['adx'] > 25.0)
    s7 = (df['Type'] == 'SELL') & (df['z_score'] > 0.60)
    
    for idx, s_mask in enumerate([s1, s2, s3, s4, s5, s6, s7], 1):
        print(f"S{idx} -> Hits TP:", len(df[s_mask & (df['Reason']=='TP')]), "Hits SL:", len(df[s_mask & (df['Reason']=='SL')]))

    # Let's combine all safe (0 TP hit) traps!
    safe_traps = []
    for name, mask in [('B1', b1), ('B2', b2), ('B3', b3), ('S1', s1), ('S2', s2), ('S3', s3), ('S4', s4), ('S5', s5), ('S6', s6), ('S7', s7)]:
        if len(df[mask & (df['Reason']=='TP')]) == 0:
            safe_traps.append((name, mask))
            print(f"Added safe trap: {name}")
            
    total_mask = pd.Series(False, index=df.index)
    for name, mask in safe_traps:
        total_mask |= mask
        
    rem_df = df[~total_mask]
    print("\n==================== COMBINED RESULT ====================")
    print("Remaining TP:", len(rem_df[rem_df['Reason']=='TP']), "Remaining SL:", len(rem_df[rem_df['Reason']=='SL']), "Remaining BE:", len(rem_df[rem_df['Reason']=='BE']))
    
    # Check Sniper dates
    sniper_dates = ['2026-07-16 23:00', '2026-07-17 21:00', '2026-07-17 23:00']
    for dt in sniper_dates:
        sub = rem_df[(rem_df['Time (BKK)'].str.contains(dt)) & (rem_df['Type'] == 'BUY')]
        print(f"Sniper {dt}: {'FOUND' if len(sub) > 0 else 'MISSING'}")
        
    print("\nRemaining SLs detail:")
    print(rem_df[rem_df['Reason']=='SL'][['Time (BKK)', 'Type', 'rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'vol_ratio', 'dist_ema50']].to_string())

if __name__ == '__main__':
    test_ideas()
