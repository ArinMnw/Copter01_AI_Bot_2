import pandas as pd

df = pd.read_csv('trade_features_18_deep.csv')
sniper_times = ['2026-07-16 23:00', '2026-07-17 21:00', '2026-07-17 23:00']

print("Original stats:")
print(f"Total: {len(df)}, TP: {len(df[df['res']=='TP'])}, SL: {len(df[df['res']=='SL'])}, BE: {len(df[df['res']=='BE'])}")
print("Snipers present:", len(df[df['time'].isin(sniper_times)]))

# Let's test various candidate filters for BUY
buy_df = df[df['type'] == 'BUY']
for r_val in [0.38, 0.40, 0.41, 0.42]:
    for p_val in [30, 32, 33.5, 35, 40]:
        rem = buy_df[(buy_df['atr_pct'] > r_val) & (buy_df['prev_range'] <= p_val)]
        snip = len(rem[rem['time'].isin(sniper_times)])
        tps = len(rem[rem['res']=='TP'])
        sls = len(rem[rem['res']=='SL'])
        if snip == 3: # all snipers must be kept!
            print(f"BUY filter (atr_pct > {r_val:.2f} and prev_range <= {p_val}): TP={tps}/9, SL={sls}/8, Snipers={snip}")

# Let's test candidate filters for SELL
sell_df = df[df['type'] == 'SELL']
for rsi_val in [48, 49.1, 50, 51, 52]:
    for z_val in [0.2, 0.3, 0.4, 0.5, 0.7]:
        rem = sell_df[(sell_df['rsi_7'] <= rsi_val) & (sell_df['z_score_10'] <= z_val)]
        tps = len(rem[rem['res']=='TP'])
        sls = len(rem[rem['res']=='SL'])
        print(f"SELL filter (rsi_7 <= {rsi_val:.1f} and z_score_10 <= {z_val:.1f}): TP={tps}/36, SL={sls}/7")

# What if we test combining the best BUY and SELL filters on the full df?
print("\n--- COMBINED SIMULATION ---")
# Let's test: BUY condition: (atr_pct > 0.40 and prev_range <= 33.5)
# SELL condition: (rsi_7 <= 50.0 and z_score_10 <= 0.4)
for b_atr in [0.38, 0.40]:
    for b_pr in [33.5, 35]:
        for s_rsi in [49.5, 50.5, 51.5]:
            for s_z in [0.3, 0.4, 0.5]:
                cond_buy = (df['type'] == 'BUY') & (df['atr_pct'] > b_atr) & (df['prev_range'] <= b_pr)
                cond_sell = (df['type'] == 'SELL') & (df['rsi_7'] <= s_rsi) & (df['z_score_10'] <= s_z)
                rem = df[cond_buy | cond_sell]
                
                snip = len(rem[rem['time'].isin(sniper_times)])
                if snip == 3:
                    tps = len(rem[rem['res']=='TP'])
                    sls = len(rem[rem['res']=='SL'])
                    bes = len(rem[rem['res']=='BE'])
                    wr = tps / (tps + sls) * 100 if (tps + sls) > 0 else 0
                    if tps >= 44 and sls <= 7:
                        print(f"Combo [BUY: atr_pct>{b_atr}, prev_range<={b_pr} | SELL: rsi_7<={s_rsi}, z10<={s_z}] -> TP:{tps}, SL:{sls}, BE:{bes}, WR:{wr:.2f}%, Snipers:{snip}")
