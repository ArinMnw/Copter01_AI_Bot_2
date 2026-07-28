import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from strategy20_13_22 import compute_indicators_df

df = pd.read_csv("700d_raw_pa_outcomes.csv")
print(f"Loaded {len(df)} setups (Wins: {(df['outcome']=='WIN').sum()}, Losses: {(df['outcome']=='LOSS').sum()})")

# Let's test individual existing filter conditions on these setups!
filters = [
    ("rsi_7 > 50.5 (SELL)", lambda r: r['signal'] == 'SELL' and r['rsi_7'] > 50.5),
    ("rsi_7 > 50.0 (SELL)", lambda r: r['signal'] == 'SELL' and r['rsi_7'] > 50.0),
    ("rsi_7 > 48.0 (SELL)", lambda r: r['signal'] == 'SELL' and r['rsi_7'] > 48.0),
    ("rsi > 60 (SELL)", lambda r: r['signal'] == 'SELL' and r['rsi'] > 60),
    ("rsi < 35 (BUY)", lambda r: r['signal'] == 'BUY' and r['rsi'] < 35),
    ("vol_ratio < 0.85 (ALL)", lambda r: r['vol_ratio'] < 0.85),
    ("vol_ratio < 1.0 (ALL)", lambda r: r['vol_ratio'] < 1.0),
    ("vol_ratio < 1.15 (ALL)", lambda r: r['vol_ratio'] < 1.15),
    ("z_score < -0.85 (SELL)", lambda r: r['signal'] == 'SELL' and r['z_score'] < -0.85),
    ("z_score > 0.85 (BUY)", lambda r: r['signal'] == 'BUY' and r['z_score'] > 0.85),
    ("body_pct < 0.50 (ALL)", lambda r: r['body_pct'] < 0.50),
    ("atr_pct < 0.20 (ALL)", lambda r: r['atr_pct'] < 0.20),
    ("adx < 15 (ALL)", lambda r: r['adx'] < 15),
    ("adx > 45 (BUY)", lambda r: r['signal'] == 'BUY' and r['adx'] > 45),
    ("adx > 45 (SELL)", lambda r: r['signal'] == 'SELL' and r['adx'] > 45),
    ("di_diff < -15 (BUY)", lambda r: r['signal'] == 'BUY' and r['di_diff'] < -15),
    ("di_diff > 15 (SELL)", lambda r: r['signal'] == 'SELL' and r['di_diff'] > 15),
    ("dist_ema50 < -20 (SELL)", lambda r: r['signal'] == 'SELL' and r['dist_ema50'] < -20),
    ("dist_ema200 < -40 (SELL)", lambda r: r['signal'] == 'SELL' and r['dist_ema200'] < -40),
]

print("\n--- INDIVIDUAL FILTER EFFICIENCY ON RAW SETUPS ---")
print(f"{'Filter Name':<30} | {'Wins Blocked':<13} | {'Losses Blocked':<15} | {'Loss/Win Ratio':<15}")
for name, cond in filters:
    blocked = df.apply(cond, axis=1)
    w_blk = (df[blocked]['outcome'] == 'WIN').sum()
    l_blk = (df[blocked]['outcome'] == 'LOSS').sum()
    ratio = (l_blk / w_blk) if w_blk > 0 else 999.0
    print(f"{name:<30} | {w_blk:<13} | {l_blk:<15} | {ratio:.2f}")
