import pandas as pd
import numpy as np

trades = pd.read_csv('s20_13_15_trades.csv')
trades['Time (BKK)'] = trades['Time (BKK)'].str.strip()

wins_times = trades[trades['Reason'] == 'TP']['Time (BKK)'].tolist()
losses_times = trades[trades['Reason'] == 'SL']['Time (BKK)'].tolist()
snipers = ['2026-07-16 23:00', '2026-07-17 21:00', '2026-07-17 23:00']

logs = []
with open('tradelog_trend.txt', 'r', encoding='utf-16') as f:
    for line in f:
        if 'TRADELOG' in line:
            parts = line.strip().split('|')
            import datetime
            utc_time = datetime.datetime.strptime(parts[2], '%Y-%m-%d %H:%M:%S')
            bkk_time = utc_time + datetime.timedelta(hours=7)
            bkk_str = bkk_time.strftime('%Y-%m-%d %H:%M')
            
            logs.append({
                'bkk_time': bkk_str,
                'side': parts[1],
                'z': float(parts[3]),
                'adx': float(parts[4]),
                'ema_dist': float(parts[5]),
                'is_win': 1 if bkk_str in wins_times else 0,
                'is_loss': 1 if bkk_str in losses_times else 0,
                'is_sniper': 1 if bkk_str in snipers else 0
            })

df = pd.DataFrame(logs).groupby('bkk_time').first().reset_index()

best_profit = 0
results = []

# Let's test combinations:
# Rule BUY: block if z > buy_z_max OR adx > buy_adx_max OR ema_dist < buy_ema_min
# Actually, let's keep it simple: Block BUY if (z > z1 AND adx > adx1)
# Block SELL if (z < z2 AND adx > adx2) OR (ema_dist > ema1)

buy_rules = []
for z1 in [-0.5, 0.0, 0.5]:
    for adx1 in [25, 30, 35, 40, 50]:
        buy_rules.append((z1, adx1))
buy_rules.append((None, None))

sell_rules = []
for z2 in [-1.0, -0.5, 0.0]:
    for adx2 in [25, 30, 35, 40, 50]:
        for ema2 in [10, 20, 50, 100, None]:
            sell_rules.append((z2, adx2, ema2))
sell_rules.append((None, None, None))

for z1, adx1 in buy_rules:
    for z2, adx2, ema2 in sell_rules:
        df['keep'] = True
        
        if z1 is not None:
            df.loc[(df['side'] == 'BUY') & (df['z'] > z1) & (df['adx'] > adx1), 'keep'] = False
            
        if z2 is not None:
            df.loc[(df['side'] == 'SELL') & (df['z'] < z2) & (df['adx'] > adx2), 'keep'] = False
        if ema2 is not None:
            df.loc[(df['side'] == 'SELL') & (df['ema_dist'] > ema2), 'keep'] = False
            
        if df[df['is_sniper'] == 1]['keep'].sum() == len(snipers):
            kw = len(df[(df['is_win'] == 1) & (df['keep'] == False)])
            kl = len(df[(df['is_loss'] == 1) & (df['keep'] == False)])
            prof = (kl * 1200) - (kw * 1500)
            if prof > best_profit and kl > 0:
                best_profit = prof
                results.append((prof, f"BUY(z>{z1}, adx>{adx1}) + SELL(z<{z2}, adx>{adx2}, ema>{ema2}) -> KW:{kw}, KL:{kl}"))

results.sort(key=lambda x: x[0], reverse=True)
for p, r in results[:15]:
    print(f"+${p}: {r}")
