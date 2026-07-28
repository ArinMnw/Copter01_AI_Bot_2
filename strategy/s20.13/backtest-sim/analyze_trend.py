import pandas as pd
import numpy as np

# Load CSV
trades = pd.read_csv('s20_13_15_trades.csv')
trades['Time (BKK)'] = trades['Time (BKK)'].str.strip()
losses_times = trades[trades['Reason'] == 'SL']['Time (BKK)'].tolist()
wins_times = trades[trades['Reason'] == 'TP']['Time (BKK)'].tolist()

sniper_times = ['2026-07-16 23:00', '2026-07-17 21:00', '2026-07-17 23:00']

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
                'is_sniper': 1 if bkk_str in sniper_times else 0
            })

df = pd.DataFrame(logs).groupby('bkk_time').first().reset_index()

wins = df[df['is_win'] == 1]
losses = df[df['is_loss'] == 1]
snipers = df[df['is_sniper'] == 1]

best_profit_diff = 0
best_rule = ""

for adx_min in np.arange(10, 45, 5):
    for z_thresh in np.arange(0, 3.0, 0.5):
        df['keep'] = True
        
        # Trend filter logic:
        # If ADX > adx_min, it's a strong trend.
        # If strong trend AND EMA distance says BULL (close > ema) AND signal is SELL -> BLOCK (keep=False)
        # If strong trend AND EMA distance says BEAR (close < ema) AND signal is BUY -> BLOCK
        
        # BUY signal against BEAR trend
        block_buy = (df['side'] == 'BUY') & (df['adx'] > adx_min) & (df['ema_dist'] < 0)
        
        # SELL signal against BULL trend
        block_sell = (df['side'] == 'SELL') & (df['adx'] > adx_min) & (df['ema_dist'] > 0)
        
        df.loc[block_buy | block_sell, 'keep'] = False
        
        if df[df['is_sniper'] == 1]['keep'].sum() == len(snipers):
            kept_wins = df[(df['is_win'] == 1) & (df['keep'] == True)]
            kept_losses = df[(df['is_loss'] == 1) & (df['keep'] == True)]
            
            killed_wins = len(wins) - len(kept_wins)
            killed_losses = len(losses) - len(kept_losses)
            
            profit_diff = (killed_losses * 1200) - (killed_wins * 1500)
            
            if profit_diff > best_profit_diff and killed_losses > 0:
                best_profit_diff = profit_diff
                best_rule = f"ADX_MIN={adx_min} -> Killed Wins:{killed_wins}, Killed Losses:{killed_losses}"

print(f"BEST TREND FILTER: {best_rule} | Appx Profit Diff: ${best_profit_diff}")

best_profit_diff = 0
best_rule = ""
for z_thresh in np.arange(0.5, 3.5, 0.25):
    df['keep'] = False
    
    # Z-Score filter logic:
    # BUY: Z < -z_thresh
    # SELL: Z > z_thresh
    buy_mask = (df['side'] == 'BUY') & (df['z'] < -z_thresh)
    sell_mask = (df['side'] == 'SELL') & (df['z'] > z_thresh)
    
    df.loc[buy_mask | sell_mask, 'keep'] = True
    
    if df[df['is_sniper'] == 1]['keep'].sum() == len(snipers):
        kept_wins = df[(df['is_win'] == 1) & (df['keep'] == True)]
        kept_losses = df[(df['is_loss'] == 1) & (df['keep'] == True)]
        
        killed_wins = len(wins) - len(kept_wins)
        killed_losses = len(losses) - len(kept_losses)
        
        profit_diff = (killed_losses * 1200) - (killed_wins * 1500)
        
        if profit_diff > best_profit_diff and killed_losses > 0:
            best_profit_diff = profit_diff
            best_rule = f"Z_THRESH={z_thresh} -> Killed Wins:{killed_wins}, Killed Losses:{killed_losses}"
            
print(f"BEST Z-SCORE FILTER: {best_rule} | Appx Profit Diff: ${best_profit_diff}")
