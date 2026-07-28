import pandas as pd
import numpy as np

# Load CSV
trades = pd.read_csv('s20_13_15_trades.csv')
trades['Time (BKK)'] = trades['Time (BKK)'].str.strip()
losses_times = trades[trades['Reason'] == 'SL']['Time (BKK)'].tolist()
wins_times = trades[trades['Reason'] == 'TP']['Time (BKK)'].tolist()

sniper_times = ['2026-07-16 23:00', '2026-07-17 21:00', '2026-07-17 23:00']

logs = []
with open('tradelog.txt', 'r', encoding='utf-16') as f:
    for line in f:
        if 'TRADELOG' in line:
            parts = line.strip().split('|')
            import datetime
            utc_time = datetime.datetime.strptime(parts[2], '%Y-%m-%d %H:%M:%S')
            bkk_time = utc_time + datetime.timedelta(hours=7)
            bkk_str = bkk_time.strftime('%Y-%m-%d %H:%M')
            
            logs.append({
                'bkk_time': bkk_str,
                'dow': bkk_time.weekday(),
                'side': parts[1],
                'rsi': float(parts[3]),
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

for rsi_buy_max in np.arange(30, 45, 1):
    for rsi_sell_min in np.arange(55, 70, 1):
        for block_thu in [True, False]:
            df['keep'] = False
            
            buy_mask = (df['side'] == 'BUY') & (df['rsi'] <= rsi_buy_max)
            sell_mask = (df['side'] == 'SELL') & (df['rsi'] >= rsi_sell_min)
            
            df.loc[buy_mask | sell_mask, 'keep'] = True
            
            if block_thu:
                # If block_thu, we only block IF they don't meet an even STRICTER condition
                # Wait, no, block_thu means completely block Thursday.
                # BUT we CANNOT completely block Thursday because Sniper 1 is on Thursday!
                # So if block_thu is true, we skip.
                continue
                
            if df[df['is_sniper'] == 1]['keep'].sum() == len(snipers):
                kept_wins = df[(df['is_win'] == 1) & (df['keep'] == True)]
                kept_losses = df[(df['is_loss'] == 1) & (df['keep'] == True)]
                
                killed_wins = len(wins) - len(kept_wins)
                killed_losses = len(losses) - len(kept_losses)
                
                profit_diff = (killed_losses * 1200) - (killed_wins * 1500)
                
                if profit_diff > best_profit_diff and killed_losses > 0:
                    best_profit_diff = profit_diff
                    best_rule = f"RSI_BUY<={rsi_buy_max}, RSI_SELL>={rsi_sell_min} -> Killed Wins:{killed_wins}, Killed Losses:{killed_losses}"

print(f"BEST RSI RULE: {best_rule} | Appx Profit Diff: ${best_profit_diff}")
