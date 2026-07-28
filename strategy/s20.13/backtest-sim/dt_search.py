import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.tree import export_text

trades = pd.read_csv('s20_13_15_trades.csv')
trades['Time (BKK)'] = trades['Time (BKK)'].str.strip()

wins_times = trades[trades['Reason'] == 'TP']['Time (BKK)'].tolist()
losses_times = trades[trades['Reason'] == 'SL']['Time (BKK)'].tolist()
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
                'side': 1 if parts[1] == 'BUY' else 0,
                'z': float(parts[3]),
                'adx': float(parts[4]),
                'ema_dist': float(parts[5]),
                'is_win': 1 if bkk_str in wins_times else 0,
                'is_loss': 1 if bkk_str in losses_times else 0,
                'is_sniper': 1 if bkk_str in sniper_times else 0
            })

df = pd.DataFrame(logs).groupby('bkk_time').first().reset_index()

# We want a classifier that separates is_win and is_loss.
# We map is_loss to 0 (bad), is_win to 1 (good).
df_train = df[(df['is_win'] == 1) | (df['is_loss'] == 1)]
X = df_train[['side', 'z', 'adx', 'ema_dist']]
y = df_train['is_win']

# We force the tree to be very simple so we don't overfit
clf = DecisionTreeClassifier(max_depth=3, min_samples_leaf=5, random_state=42)
clf.fit(X, y)

print(export_text(clf, feature_names=['side', 'z', 'adx', 'ema_dist']))

df_train['pred'] = clf.predict(X)
print("Killed Wins:", len(df_train[(df_train['is_win'] == 1) & (df_train['pred'] == 0)]))
print("Killed Losses:", len(df_train[(df_train['is_loss'] == 1) & (df_train['pred'] == 0)]))
print("Killed Snipers:", len(df_train[(df_train['is_sniper'] == 1) & (df_train['pred'] == 0)]))

# Let's try multiple hyperparams
best_profit = 0
for max_depth in [2, 3]:
    for min_leaf in [2, 3, 5, 8]:
        clf = DecisionTreeClassifier(max_depth=max_depth, min_samples_leaf=min_leaf, random_state=42, class_weight={0: 1.5, 1: 1.0})
        clf.fit(X, y)
        preds = clf.predict(X)
        df_train['pred'] = preds
        
        killed_wins = len(df_train[(df_train['is_win'] == 1) & (df_train['pred'] == 0)])
        killed_losses = len(df_train[(df_train['is_loss'] == 1) & (df_train['pred'] == 0)])
        killed_snipers = len(df_train[(df_train['is_sniper'] == 1) & (df_train['pred'] == 0)])
        
        if killed_snipers == 0 and killed_losses > 0:
            profit = (killed_losses * 1200) - (killed_wins * 1500)
            if profit > best_profit:
                best_profit = profit
                print(f"DEPTH={max_depth} LEAF={min_leaf} | Killed Wins: {killed_wins}, Killed Losses: {killed_losses} | Diff: ${profit}")
                print(export_text(clf, feature_names=['side', 'z', 'adx', 'ema_dist']))
