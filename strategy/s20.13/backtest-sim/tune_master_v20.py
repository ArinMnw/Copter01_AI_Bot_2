import pandas as pd
import numpy as np

def run_tuning():
    df = pd.read_csv('trades_365d_fast_features.csv')
    print("Initial -> TP:", len(df[df['Reason']=='TP']), "SL:", len(df[df['Reason']=='SL']), "BE:", len(df[df['Reason']=='BE']))
    
    # 1. SELL TRAPS
    # Trap S1: Short-term oversold in Bullish/Neutral market
    s1 = (df['Type'] == 'SELL') & (df['rsi_7'] < 41.5) & (df['di_diff'] > 0.5)
    
    # Trap S2: Low ADX and near/above EMA50 (Tuned to 0 TP hit!)
    s2 = (df['Type'] == 'SELL') & (df['adx'] < 20.2) & (df['dist_ema50'] > -12.0)
    
    # Trap S3: Low volume in oversold territory
    s3 = (df['Type'] == 'SELL') & (df['vol_ratio'] < 1.90) & (df['rsi'] < 39.0)
    
    # Trap S4: Selling near upper BB during low volatility
    s4 = (df['Type'] == 'SELL') & (df['z_score'] > 0.20) & (df['atr_pct'] < 0.31)
    
    # Trap S5: RSI momentum divergence (High RSI14 but low RSI7)
    s5 = (df['Type'] == 'SELL') & (df['rsi'] > 53.0) & (df['rsi_7'] < 37.0)

    # Trap S6: Exhaustion selling climax below lower BB
    s6 = (df['Type'] == 'SELL') & (df['z_score'] < -2.10) & (df['vol_ratio'] > 2.20)

    # Trap S7: Selling far above EMA50 during Bullish DI dominance
    s7 = (df['Type'] == 'SELL') & (df['dist_ema50'] > 15.0) & (df['di_diff'] > 0.0)

    # 2. BUY TRAPS
    # Trap B1: Bearish momentum discrepancy (Tuned to 0 TP hit!)
    b1 = (df['Type'] == 'BUY') & (df['rsi'] < 45.0) & (df['z_score'] > 0.05)
    
    # Trap B2: Extremely low volume breakout
    b2 = (df['Type'] == 'BUY') & (df['vol_ratio'] < 0.55)

    # Trap B3: High ATR chop in oversold BUY
    b3 = (df['Type'] == 'BUY') & (df['atr_pct'] > 0.55) & (df['rsi'] < 46.0)

    traps = [('S1', s1), ('S2', s2), ('S3', s3), ('S4', s4), ('S5', s5), ('S6', s6), ('S7', s7), ('B1', b1), ('B2', b2), ('B3', b3)]
    
    print("\n--- INDIVIDUAL TRAP CHECK ---")
    valid_traps = []
    for name, mask in traps:
        tp_hit = len(df[mask & (df['Reason']=='TP')])
        sl_hit = len(df[mask & (df['Reason']=='SL')])
        status = "PASS" if tp_hit == 0 else f"FAIL (TP={tp_hit})"
        print(f"[{status:10s}] {name:5s} | Hits TP: {tp_hit} | Hits SL: {sl_hit}")
        if tp_hit == 0 and sl_hit > 0:
            valid_traps.append((name, mask))
            
    # Combine all PASS traps
    comb = pd.Series(False, index=df.index)
    for name, mask in valid_traps:
        comb |= mask
        print(f"Adding safe trap: {name}")
        
    rem_df = df[~comb]
    print("\n==================== TUNED V20 COMBINED RESULT ====================")
    print("Remaining TP:", len(rem_df[rem_df['Reason']=='TP']), "| Remaining SL:", len(rem_df[rem_df['Reason']=='SL']), "| Remaining BE:", len(rem_df[rem_df['Reason']=='BE']))
    total_trades = len(rem_df)
    win_rate_classic = (len(rem_df[rem_df['Reason']=='TP']) / total_trades) * 100
    win_rate_winloss = (len(rem_df[rem_df['Reason']=='TP']) / (len(rem_df[rem_df['Reason']=='TP']) + len(rem_df[rem_df['Reason']=='SL']))) * 100
    print(f"Total Trades: {total_trades} | Win Rate (Classic): {win_rate_classic:.2f}% | Win Rate (Win/Loss): {win_rate_winloss:.2f}%")
    
    # Check Sniper dates
    sniper_dates = ['2026-07-16 23:00', '2026-07-17 21:00', '2026-07-17 23:00']
    for dt in sniper_dates:
        sub = rem_df[(rem_df['Time (BKK)'].str.contains(dt)) & (rem_df['Type'] == 'BUY')]
        print(f"Sniper {dt}: {'FOUND' if len(sub) > 0 else 'MISSING'}")

    print("\nRemaining SLs:")
    print(rem_df[rem_df['Reason']=='SL'][['Time (BKK)', 'Type', 'rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'vol_ratio', 'dist_ema50']].to_string())

if __name__ == '__main__':
    run_tuning()
