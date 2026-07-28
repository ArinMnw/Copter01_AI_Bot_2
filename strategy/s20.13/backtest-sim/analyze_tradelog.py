import pandas as pd
import numpy as np

# Load CSV
trades = pd.read_csv('s20_13_15_trades.csv')
trades['Time (BKK)'] = trades['Time (BKK)'].str.strip()
losses_times = trades[trades['Reason'] == 'SL']['Time (BKK)'].tolist()
wins_times = trades[trades['Reason'] == 'TP']['Time (BKK)'].tolist()

sniper_times = ['2026-07-16 23:00', '2026-07-17 21:00', '2026-07-17 23:00']

# Parse tradelog.txt
logs = []
with open('tradelog.txt', 'r', encoding='utf-16') as f:
    for line in f:
        if 'TRADELOG' in line:
            parts = line.strip().split('|')
            # Format: TRADELOG|BUY|2026-03-02 23:00:00|RSI|BODY|UW|LW|RANGE/ATR
            # Note: The time in TRADELOG is MT5 UTC time. Backtester BKK time = MT5 time + 7 hours!
            # Let's adjust UTC -> BKK to match!
            import datetime
            utc_time = datetime.datetime.strptime(parts[2], '%Y-%m-%d %H:%M:%S')
            bkk_time = utc_time + datetime.timedelta(hours=7)
            bkk_str = bkk_time.strftime('%Y-%m-%d %H:%M')
            
            logs.append({
                'bkk_time': bkk_str,
                'side': parts[1],
                'rsi': float(parts[3]),
                'body': float(parts[4]),
                'uw': float(parts[5]),
                'lw': float(parts[6]),
                'ratr': float(parts[7]),
                'is_win': 1 if bkk_str in wins_times else 0,
                'is_loss': 1 if bkk_str in losses_times else 0,
                'is_sniper': 1 if bkk_str in sniper_times else 0
            })

df = pd.DataFrame(logs)
# df could have multiple entries for same time because backtest scans every tick.
# Group by bkk_time and take the first
df = df.groupby('bkk_time').first().reset_index()

wins = df[df['is_win'] == 1]
losses = df[df['is_loss'] == 1]
snipers = df[df['is_sniper'] == 1]

print(f"Total Wins matched: {len(wins)}")
print(f"Total Losses matched: {len(losses)}")
print(f"Total Snipers matched: {len(snipers)}")

# Grid Search
best_profit_diff = 0
best_rule = ""

# Base metrics from .15
base_win_count = len(wins)
base_loss_count = len(losses)

for lw_thresh in np.arange(0, 0.4, 0.05):
    for uw_thresh in np.arange(0, 0.4, 0.05):
        for ratr_min in np.arange(0.8, 2.0, 0.1):
            for ratr_max in [10.0, 3.0, 4.0, 5.0]:
                for body_min in np.arange(0.2, 0.6, 0.1):
                    # Filter logic:
                    # Keep if:
                    # BUY: lw >= lw_thresh AND ratr >= ratr_min AND ratr <= ratr_max AND body >= body_min
                    # SELL: uw >= uw_thresh AND ratr >= ratr_min AND ratr <= ratr_max AND body >= body_min
                    
                    df['keep'] = False
                    
                    buy_mask = (df['side'] == 'BUY') & (df['lw'] >= lw_thresh) & (df['ratr'] >= ratr_min) & (df['ratr'] <= ratr_max) & (df['body'] >= body_min)
                    sell_mask = (df['side'] == 'SELL') & (df['uw'] >= uw_thresh) & (df['ratr'] >= ratr_min) & (df['ratr'] <= ratr_max) & (df['body'] >= body_min)
                    
                    df.loc[buy_mask | sell_mask, 'keep'] = True
                    
                    # Check Snipers
                    if df[df['is_sniper'] == 1]['keep'].sum() == len(snipers):
                        # Snipers preserved!
                        kept_wins = df[(df['is_win'] == 1) & (df['keep'] == True)]
                        kept_losses = df[(df['is_loss'] == 1) & (df['keep'] == True)]
                        
                        killed_wins = base_win_count - len(kept_wins)
                        killed_losses = base_loss_count - len(kept_losses)
                        
                        # Approximating profit difference: Win = +$1500, Loss = -$1200
                        profit_diff = (killed_losses * 1200) - (killed_wins * 1500)
                        
                        if profit_diff > best_profit_diff and killed_losses > 0:
                            best_profit_diff = profit_diff
                            best_rule = f"lw>={lw_thresh:.2f}, uw>={uw_thresh:.2f}, ratr>={ratr_min:.2f}-{ratr_max:.2f}, body>={body_min:.2f} -> Killed Wins:{killed_wins}, Killed Losses:{killed_losses}"

print(f"BEST FILTER: {best_rule} | Appx Profit Diff: ${best_profit_diff}")
