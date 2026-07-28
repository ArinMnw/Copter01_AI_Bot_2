import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier, export_text

df = pd.read_csv('trade_features_18_deep.csv')
sniper_times = ['2026-07-16 23:00', '2026-07-17 21:00', '2026-07-17 23:00']

# We want to predict res == 'SL' (1 for loss, 0 for win)
df['target'] = (df['res'] == 'SL').astype(int)

feature_cols = [c for c in df.columns if c not in ['time', 'type', 'res', 'pnl', 'target']]

print("=== BUY TRADES DECISION TREE ===")
buy_df = df[df['type'] == 'BUY'].copy()
X_buy = buy_df[feature_cols].fillna(0)
y_buy = buy_df['target']

for depth in [1, 2, 3]:
    dt = DecisionTreeClassifier(max_depth=depth, class_weight='balanced', random_state=42)
    dt.fit(X_buy, y_buy)
    print(f"\n--- Depth {depth} ---")
    print(export_text(dt, feature_names=feature_cols))

print("\n=== SELL TRADES DECISION TREE ===")
sell_df = df[df['type'] == 'SELL'].copy()
X_sell = sell_df[feature_cols].fillna(0)
y_sell = sell_df['target']

for depth in [1, 2, 3]:
    dt = DecisionTreeClassifier(max_depth=depth, class_weight='balanced', random_state=42)
    dt.fit(X_sell, y_sell)
    print(f"\n--- Depth {depth} ---")
    print(export_text(dt, feature_names=feature_cols))

# Let's also check manual correlation with SL
print("\n=== BUY CORRELATION WITH LOSS ===")
print(buy_df[feature_cols].corrwith(y_buy).sort_values(ascending=False))

print("\n=== SELL CORRELATION WITH LOSS ===")
print(sell_df[feature_cols].corrwith(y_sell).sort_values(ascending=False))
