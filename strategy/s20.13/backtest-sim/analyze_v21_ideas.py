import pandas as pd
import numpy as np

df = pd.read_csv('v20_all_trades_features.csv')
print(f"Total rows in v20 trades: {len(df)}")

wins = df[df['outcome'] == 'WIN']
losses = df[df['outcome'] == 'LOSS']

print(f"Wins: {len(wins)} | Losses: {len(losses)}")

# Check Sniper BUY orders in mid-July 2026
sniper = df[(df['time'].str.contains('2026-07-16|2026-07-17')) & (df['signal'] == 'BUY')]
print("\n--- SNIPER BUY ORDERS ---")
print(sniper[['time', 'signal', 'outcome', 'rsi', 'rsi_7', 'adx', 'di_diff', 'vol_ratio', 'z_score', 'body_pct', 'atr_pct', 'dist_ema50', 'hour']])

print("\n--- TEST FILTER IDEAS ---")

# Idea 1: SELL when Z-score < -2.0 (Extreme lower Bollinger band breakdown trap in SELL)
# Notice: 2025-09-17 19:00 (Z=-2.45), 2025-09-30 (Z=-2.15), 2025-10-02 (Z=-2.68), 2026-01-16 (Z=-3.29), 2026-02-12 (Z=-3.95)
# All 5 of these are SELL losses where Z < -2.1! What if we block SELL when z_score < -2.0?
sell_z_loss = len(losses[(losses['signal'] == 'SELL') & (losses['z_score'] < -2.0)])
sell_z_win = len(wins[(wins['signal'] == 'SELL') & (wins['z_score'] < -2.0)])
print(f"Idea 1 (SELL Z < -2.0 block): Blocks {sell_z_loss} losses, {sell_z_win} wins")

# Idea 2: SELL when ADX > 60 (Extreme trend exhaustion in SELL)
# Notice: 2025-10-14 06:00 (ADX=68.89)
sell_adx_loss = len(losses[(losses['signal'] == 'SELL') & (losses['adx'] > 60.0)])
sell_adx_win = len(wins[(wins['signal'] == 'SELL') & (wins['adx'] > 60.0)])
print(f"Idea 2 (SELL ADX > 60.0 block): Blocks {sell_adx_loss} losses, {sell_adx_win} wins")

# Idea 3: SELL when lower_wick_pct > 0.40 (High lower wick rejection in SELL candle)
# Notice: 2025-12-11 (lWick=0.48), 2026-01-16 (lWick=0.41), 2026-02-12 (lWick=0.41), 2026-02-19 (lWick=0.8)
sell_lwick_loss = len(losses[(losses['signal'] == 'SELL') & (losses['lower_wick_pct'] > 0.40)])
sell_lwick_win = len(wins[(wins['signal'] == 'SELL') & (wins['lower_wick_pct'] > 0.40)])
print(f"Idea 3 (SELL lower_wick_pct > 0.40 block): Blocks {sell_lwick_loss} losses, {sell_lwick_win} wins")

# Idea 4: SELL when ATR% > 0.60 (Extreme volatility spike in SELL)
# Notice: 2026-02-12 (ATR%=0.69)
sell_atr_loss = len(losses[(losses['signal'] == 'SELL') & (losses['atr_pct'] > 0.60)])
sell_atr_win = len(wins[(wins['signal'] == 'SELL') & (wins['atr_pct'] > 0.60)])
print(f"Idea 4 (SELL ATR% > 0.60 block): Blocks {sell_atr_loss} losses, {sell_atr_win} wins")

# Idea 5: BUY when Dist_EMA50 < -35 (Extreme distance below EMA50 trap in BUY)
# Notice: 2025-11-17 07:00 (dEMA50 = -39.47)
buy_dema_loss = len(losses[(losses['signal'] == 'BUY') & (losses['dist_ema50'] < -35.0)])
buy_dema_win = len(wins[(wins['signal'] == 'BUY') & (wins['dist_ema50'] < -35.0)])
print(f"Idea 5 (BUY dist_ema50 < -35.0 block): Blocks {buy_dema_loss} losses, {buy_dema_win} wins")

# Idea 6: SELL when RSI7 > 70 (Overbought spike during SELL signal)
# Notice: 2025-12-23 21:00 (RSI7=78.6)
sell_rsi7_loss = len(losses[(losses['signal'] == 'SELL') & (losses['rsi_7'] > 70.0)])
sell_rsi7_win = len(wins[(wins['signal'] == 'SELL') & (wins['rsi_7'] > 70.0)])
print(f"Idea 6 (SELL RSI7 > 70.0 block): Blocks {sell_rsi7_loss} losses, {sell_rsi7_win} wins")

# Idea 7: SELL when DI_diff > 6.0 and Vol_Ratio < 1.9 (Bullish DI dominance without extreme volume in SELL)
# Notice: 2025-12-11 (DIdf=13.91, Vol=1.07), 2025-12-18 (DIdf=7.03, Vol=1.88), 2026-01-06 (DIdf=9.4, Vol=1.06), 2026-01-09 (DIdf=8.54, Vol=1.41)
sell_didf_loss = len(losses[(losses['signal'] == 'SELL') & (losses['di_diff'] > 6.0) & (losses['vol_ratio'] < 1.9)])
sell_didf_win = len(wins[(wins['signal'] == 'SELL') & (wins['di_diff'] > 6.0) & (wins['vol_ratio'] < 1.9)])
print(f"Idea 7 (SELL di_diff > 6.0 & vol_ratio < 1.9 block): Blocks {sell_didf_loss} losses, {sell_didf_win} wins")

# Let's check combination of all 7 ideas!
cond1 = (df['signal'] == 'SELL') & (df['z_score'] < -2.0)
cond2 = (df['signal'] == 'SELL') & (df['adx'] > 60.0)
cond3 = (df['signal'] == 'SELL') & (df['lower_wick_pct'] > 0.40)
cond4 = (df['signal'] == 'SELL') & (df['atr_pct'] > 0.60)
cond5 = (df['signal'] == 'BUY') & (df['dist_ema50'] < -35.0)
cond6 = (df['signal'] == 'SELL') & (df['rsi_7'] > 70.0)
cond7 = (df['signal'] == 'SELL') & (df['di_diff'] > 6.0) & (df['vol_ratio'] < 1.9)

combined = cond1 | cond2 | cond3 | cond4 | cond5 | cond6 | cond7
print(f"\n--- COMBINED 7 RULES ---")
print(f"Total Losses Blocked: {len(df[(df['outcome'] == 'LOSS') & combined])} / 20")
print(f"Total Wins Blocked  : {len(df[(df['outcome'] == 'WIN') & combined])} / 48")
