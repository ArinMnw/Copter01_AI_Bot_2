import pandas as pd

trades = pd.read_csv('s20_13_15_trades.csv')
trades['Time (BKK)'] = trades['Time (BKK)'].str.strip()

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
            })

df = pd.DataFrame(logs).groupby('bkk_time').first().reset_index()

merged = pd.merge(trades, df, left_on='Time (BKK)', right_on='bkk_time', how='inner')

print("=== LOSSES ===")
print(merged[merged['Reason'] == 'SL'][['Time (BKK)', 'side', 'z', 'adx', 'ema_dist']].to_string())

print("\n=== WINS ===")
print(merged[merged['Reason'] == 'TP'][['Time (BKK)', 'side', 'z', 'adx', 'ema_dist']].to_string())

print("\n=== SNIPERS ===")
snipers = ['2026-07-16 23:00', '2026-07-17 21:00', '2026-07-17 23:00']
print(merged[merged['Time (BKK)'].isin(snipers)][['Time (BKK)', 'side', 'z', 'adx', 'ema_dist']].to_string())
