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

# Rule type 1: Block BUY if condition
for z_max in np.arange(-2.0, 2.0, 0.2):
    for adx_min in np.arange(10, 60, 5):
        # Block BUY if z > z_max AND adx > adx_min
        df['keep'] = True
        df.loc[(df['side'] == 'BUY') & (df['z'] > z_max) & (df['adx'] > adx_min), 'keep'] = False
        
        if df[df['is_sniper'] == 1]['keep'].sum() == len(snipers):
            kw = len(df[(df['is_win'] == 1) & (df['keep'] == False)])
            kl = len(df[(df['is_loss'] == 1) & (df['keep'] == False)])
            prof = (kl * 1200) - (kw * 1500)
            if prof > 0 and kl > 0:
                results.append((prof, f"Block BUY if z > {z_max:.1f} and adx > {adx_min} -> KW:{kw}, KL:{kl}"))

# Rule type 2: Block SELL if condition
for z_min in np.arange(-2.0, 2.0, 0.2):
    for adx_min in np.arange(10, 60, 5):
        # Block SELL if z < z_min AND adx > adx_min
        df['keep'] = True
        df.loc[(df['side'] == 'SELL') & (df['z'] < z_min) & (df['adx'] > adx_min), 'keep'] = False
        
        if df[df['is_sniper'] == 1]['keep'].sum() == len(snipers):
            kw = len(df[(df['is_win'] == 1) & (df['keep'] == False)])
            kl = len(df[(df['is_loss'] == 1) & (df['keep'] == False)])
            prof = (kl * 1200) - (kw * 1500)
            if prof > 0 and kl > 0:
                results.append((prof, f"Block SELL if z < {z_min:.1f} and adx > {adx_min} -> KW:{kw}, KL:{kl}"))

results.sort(key=lambda x: x[0], reverse=True)
for p, r in results[:10]:
    print(f"+${p}: {r}")
if not results:
    print("NO VALID COMBINATIONS FOUND THAT INCREASE PROFIT!")
