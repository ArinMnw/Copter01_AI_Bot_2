import pandas as pd
import numpy as np

def run_combo_test():
    df = pd.read_csv('trades_365d_fast_features.csv')
    print("Initial -> TP:", len(df[df['Reason']=='TP']), "SL:", len(df[df['Reason']=='SL']), "BE:", len(df[df['Reason']=='BE']))
    
    # Sniper trade dates
    sniper_dates = ['2026-07-16 23:00', '2026-07-17 21:00', '2026-07-17 23:00']
    
    # Let's test a list of candidate SELL filters that each drop 0 TPs
    sell_rules = [
        ("SELL Rule 1: RSI7 < 41.5 and DI_Diff > 0.85", lambda d: (d['Type'] == 'SELL') & (d['rsi_7'] < 41.5) & (d['di_diff'] > 0.85)),
        ("SELL Rule 2: ATR% < 0.325 and DI_Diff > 0.85", lambda d: (d['Type'] == 'SELL') & (d['atr_pct'] < 0.325) & (d['di_diff'] > 0.85)),
        ("SELL Rule 3: ADX < 20.5 and dist_ema50 > -12.5", lambda d: (d['Type'] == 'SELL') & (d['adx'] < 20.5) & (d['dist_ema50'] > -12.5)),
        ("SELL Rule 4: ATR% < 0.325 and Z_Score > 0.20", lambda d: (d['Type'] == 'SELL') & (d['atr_pct'] < 0.325) & (d['z_score'] > 0.20)),
        ("SELL Rule 5: RSI > 53.0 and RSI7 < 37.5", lambda d: (d['Type'] == 'SELL') & (d['rsi'] > 53.0) & (d['rsi_7'] < 37.5)),
        ("SELL Rule 6: dist_ema50 > 15.0 and body_pct < 0.58", lambda d: (d['Type'] == 'SELL') & (d['dist_ema50'] > 15.0) & (d['body_pct'] < 0.58)),
        ("SELL Rule 7: ATR% < 0.38 and Vol_Ratio > 2.00", lambda d: (d['Type'] == 'SELL') & (d['atr_pct'] < 0.38) & (d['vol_ratio'] > 2.00)),
        ("SELL Rule 8: Z_Score > -0.50 and RSI7 < 37.0", lambda d: (d['Type'] == 'SELL') & (d['z_score'] > -0.50) & (d['rsi_7'] < 37.0)),
        ("SELL Rule 9: dist_ema50 > 5.0 and RSI7 < 37.5", lambda d: (d['Type'] == 'SELL') & (d['dist_ema50'] > 5.0) & (d['rsi_7'] < 37.5)),
        ("SELL Rule 10: Vol_Ratio < 1.95 and RSI < 39.5", lambda d: (d['Type'] == 'SELL') & (d['vol_ratio'] < 1.95) & (d['rsi'] < 39.5)),
        ("SELL Rule 11: ATR% < 0.35 and Z_Score > 0.40", lambda d: (d['Type'] == 'SELL') & (d['atr_pct'] < 0.35) & (d['z_score'] > 0.40)),
        ("SELL Rule 12: dist_ema50 > -24.0 and Vol_Ratio > 2.00", lambda d: (d['Type'] == 'SELL') & (d['dist_ema50'] > -24.0) & (d['vol_ratio'] > 2.00)),
        ("SELL Rule 13: DI_Diff > -1.0 and RSI7 < 37.0", lambda d: (d['Type'] == 'SELL') & (d['di_diff'] > -1.0) & (d['rsi_7'] < 37.0)),
        ("SELL Rule 14: Z_Score > 0.20 and ATR% < 0.31", lambda d: (d['Type'] == 'SELL') & (d['z_score'] > 0.20) & (d['atr_pct'] < 0.31)),
        ("SELL Rule 15: ADX > 45.0 and RSI7 > 40.0", lambda d: (d['Type'] == 'SELL') & (d['adx'] > 45.0) & (d['rsi_7'] > 40.0)),
        ("SELL Rule 16: dist_ema50 > 25.0", lambda d: (d['Type'] == 'SELL') & (d['dist_ema50'] > 25.0)),
        ("SELL Rule 17: RSI > 56.0", lambda d: (d['Type'] == 'SELL') & (d['rsi'] > 56.0))
    ]
    
    # Let's check each rule individually
    print("\n--- INDIVIDUAL RULE IMPACT ---")
    for name, func in sell_rules:
        mask = func(df)
        tp_drop = len(df[mask & (df['Reason']=='TP')])
        sl_drop = len(df[mask & (df['Reason']=='SL')])
        if tp_drop == 0 and sl_drop > 0:
            print(f"[PASS] {name:45s} | Drops SL: {sl_drop:2d} | Drops TP: {tp_drop}")
        elif tp_drop > 0:
            print(f"[FAIL] {name:45s} | Drops SL: {sl_drop:2d} | Drops TP: {tp_drop}")
            
    # Now let's combine ALL valid 0-TP rules
    valid_rules = [func for name, func in sell_rules if len(df[func(df) & (df['Reason']=='TP')]) == 0]
    
    combined_mask = pd.Series(False, index=df.index)
    for func in valid_rules:
        combined_mask |= func(df)
        
    print("\n--- COMBINED SELL RULES IMPACT ---")
    rem_df = df[~combined_mask]
    print("Remaining TP:", len(rem_df[rem_df['Reason']=='TP']), "Remaining SL:", len(rem_df[rem_df['Reason']=='SL']))
    print("Remaining SELL SLs:", len(rem_df[(rem_df['Type']=='SELL') & (rem_df['Reason']=='SL')]))
    
    # Let's inspect the remaining SELL SLs to see if we can drop even more!
    rem_sell_sls = rem_df[(rem_df['Type']=='SELL') & (rem_df['Reason']=='SL')]
    print("\nRemaining SELL SLs:")
    print(rem_sell_sls[['Time (BKK)', 'rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'body_pct', 'vol_ratio', 'dist_ema50', 'hour']].to_string())

if __name__ == '__main__':
    run_combo_test()
