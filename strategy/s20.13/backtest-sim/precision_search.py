import pandas as pd
import numpy as np

def run_precision_search():
    df = pd.read_csv('trades_365d_fast_features.csv')
    
    # Let's check all 35 TPs of SELL to see what their min/max values are for key features
    sell_tps = df[(df['Type']=='SELL') & (df['Reason']=='TP')]
    sell_sls = df[(df['Type']=='SELL') & (df['Reason']=='SL')]
    
    print("=== SELL TP EXTREMES (35 trades) ===")
    print(sell_tps[['rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'vol_ratio', 'dist_ema50']].describe().T[['min', '50%', 'max']])
    
    print("\n=== SELL SL EXTREMES (31 trades) ===")
    print(sell_sls[['rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'vol_ratio', 'dist_ema50']].describe().T[['min', '50%', 'max']])

    # Let's test specific high-confidence safe boundaries
    # 1. RSI7 and DI_Diff
    # What is the max di_diff among SELL TPs when rsi_7 < 41?
    tps_low_rsi7 = sell_tps[sell_tps['rsi_7'] < 42.0]
    print("\nWhen SELL TP has rsi_7 < 42.0, max di_diff is:", tps_low_rsi7['di_diff'].max())
    
    # Let's test candidate SELL rules with 0 TP hit:
    sell_candidates = [
        ("SELL Rule 1 (Oversold Bullish DI): rsi_7 < 42.0 and di_diff > 0.50", lambda d: (d['Type']=='SELL') & (d['rsi_7'] < 42.0) & (d['di_diff'] > 0.50)),
        ("SELL Rule 2 (Low ADX Uptrend): adx < 21.0 and dist_ema50 > -15.0", lambda d: (d['Type']=='SELL') & (d['adx'] < 21.0) & (d['dist_ema50'] > -15.0)),
        ("SELL Rule 3 (Low Vol Oversold): vol_ratio < 1.90 and rsi < 39.0", lambda d: (d['Type']=='SELL') & (d['vol_ratio'] < 1.90) & (d['rsi'] < 39.0)),
        ("SELL Rule 4 (Low ATR Upper BB): z_score > 0.20 and atr_pct < 0.31", lambda d: (d['Type']=='SELL') & (d['z_score'] > 0.20) & (d['atr_pct'] < 0.31)),
        ("SELL Rule 5 (High RSI Momentum Trap): rsi > 53.0 and rsi_7 < 37.0", lambda d: (d['Type']=='SELL') & (d['rsi'] > 53.0) & (d['rsi_7'] < 37.0)),
        ("SELL Rule 6 (Far Above EMA50 Chop): dist_ema50 > 25.0 and adx < 30.0", lambda d: (d['Type']=='SELL') & (d['dist_ema50'] > 25.0) & (d['adx'] < 30.0)),
        ("SELL Rule 7 (High DI_Diff Trap): di_diff > 6.0 and rsi > 50.0", lambda d: (d['Type']=='SELL') & (d['di_diff'] > 6.0) & (d['rsi'] > 50.0)),
        ("SELL Rule 8 (Extreme Z-Score Trap): z_score < -2.40 and vol_ratio > 2.5", lambda d: (d['Type']=='SELL') & (d['z_score'] < -2.40) & (d['vol_ratio'] > 2.5)),
        ("SELL Rule 9 (Low Volatility High EMA): dist_ema50 > 15.0 and atr_pct < 0.40", lambda d: (d['Type']=='SELL') & (d['dist_ema50'] > 15.0) & (d['atr_pct'] < 0.40)),
        ("SELL Rule 10 (Strong Bullish DI Diff): di_diff > 2.5 and atr_pct < 0.50", lambda d: (d['Type']=='SELL') & (d['di_diff'] > 2.5) & (d['atr_pct'] < 0.50))
    ]
    
    print("\n--- TESTING SELL CANDIDATES ---")
    valid_sell = []
    for name, func in sell_candidates:
        tp_hit = len(df[func(df) & (df['Reason']=='TP')])
        sl_hit = len(df[func(df) & (df['Reason']=='SL')])
        status = "PASS" if tp_hit == 0 else f"FAIL (TP={tp_hit})"
        print(f"[{status:10s}] {name:65s} | Drops SL: {sl_hit}")
        if tp_hit == 0 and sl_hit > 0:
            valid_sell.append((name, func))
            
    # Now let's test candidate BUY rules
    buy_tps = df[(df['Type']=='BUY') & (df['Reason']=='TP')]
    buy_sls = df[(df['Type']=='BUY') & (df['Reason']=='SL')]
    print("\n=== BUY TP EXTREMES (15 trades) ===")
    print(buy_tps[['rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'vol_ratio', 'dist_ema50']].describe().T[['min', '50%', 'max']])
    print("\n=== BUY SL EXTREMES (4 trades) ===")
    print(buy_sls[['rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'vol_ratio', 'dist_ema50']].describe().T[['min', '50%', 'max']])

    buy_candidates = [
        ("BUY Rule 1: vol_ratio < 0.65", lambda d: (d['Type']=='BUY') & (d['vol_ratio'] < 0.65)),
        ("BUY Rule 2: atr_pct > 0.55 and rsi < 47.0", lambda d: (d['Type']=='BUY') & (d['atr_pct'] > 0.55) & (d['rsi'] < 47.0)),
        ("BUY Rule 3: dist_ema50 < -25.0 and vol_ratio < 1.25", lambda d: (d['Type']=='BUY') & (d['dist_ema50'] < -25.0) & (d['vol_ratio'] < 1.25)),
        ("BUY Rule 4: adx > 45.0 and di_diff < -8.0", lambda d: (d['Type']=='BUY') & (d['adx'] > 45.0) & (d['di_diff'] < -8.0)),
        ("BUY Rule 5: rsi_7 < 47.0 and atr_pct > 0.48 and di_diff < -8.5", lambda d: (d['Type']=='BUY') & (d['rsi_7'] < 47.0) & (d['atr_pct'] > 0.48) & (d['di_diff'] < -8.5))
    ]

    print("\n--- TESTING BUY CANDIDATES ---")
    valid_buy = []
    for name, func in buy_candidates:
        tp_hit = len(df[func(df) & (df['Reason']=='TP')])
        sl_hit = len(df[func(df) & (df['Reason']=='SL')])
        status = "PASS" if tp_hit == 0 else f"FAIL (TP={tp_hit})"
        print(f"[{status:10s}] {name:65s} | Drops SL: {sl_hit}")
        if tp_hit == 0 and sl_hit > 0:
            valid_buy.append((name, func))
            
    # Combine all valid
    comb_mask = pd.Series(False, index=df.index)
    for _, func in valid_sell + valid_buy:
        comb_mask |= func(df)
        
    rem_df = df[~comb_mask]
    print("\n==================== TOTAL COMBINED IMPACT ====================")
    print("Remaining TP:", len(rem_df[rem_df['Reason']=='TP']), "| Remaining SL:", len(rem_df[rem_df['Reason']=='SL']), "| Remaining BE:", len(rem_df[rem_df['Reason']=='BE']))
    print("Win Rate:", round(len(rem_df[rem_df['Reason']=='TP']) / (len(rem_df[rem_df['Reason']=='TP']) + len(rem_df[rem_df['Reason']=='SL'])) * 100, 2), "%")
    
    # Check Sniper dates
    sniper_dates = ['2026-07-16 23:00', '2026-07-17 21:00', '2026-07-17 23:00']
    for dt in sniper_dates:
        sub = rem_df[(rem_df['Time (BKK)'].str.contains(dt)) & (rem_df['Type'] == 'BUY')]
        print(f"Sniper {dt}: {'FOUND' if len(sub) > 0 else 'MISSING'}")

    print("\nRemaining SLs:")
    print(rem_df[rem_df['Reason']=='SL'][['Time (BKK)', 'Type', 'rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'vol_ratio', 'dist_ema50']].to_string())

if __name__ == '__main__':
    run_precision_search()
