import pandas as pd
import numpy as np
import itertools

df = pd.read_csv('v22_700d_all_trades_features.csv')
wins = df[df['outcome'] == 'WIN']
losses = df[df['outcome'] == 'LOSS']

print(f"Searching v23 precision rules on 700-day dataset: {len(losses)} losses vs {len(wins)} wins...")

sell_wins = wins[wins['signal'] == 'SELL']
sell_losses = losses[losses['signal'] == 'SELL']

features = [
    ('rsi', [35, 40, 42, 45, 48, 50, 52, 53, 55, 57, 58, 60], ['<', '>']),
    ('rsi_7', [30, 35, 40, 45, 47, 50, 52, 55, 60, 65], ['<', '>']),
    ('adx', [20, 22, 25, 27, 30, 32, 35, 38, 40, 42, 45, 50, 60], ['<', '>']),
    ('di_diff', [-20, -15, -10, -5, -3, -1, 0, 1, 3, 5, 10, 15], ['<', '>']),
    ('vol_ratio', [0.7, 0.8, 0.9, 1.0, 1.1, 1.3, 1.5, 1.7, 1.9, 2.0, 2.2], ['<', '>']),
    ('z_score', [-1.5, -1.0, -0.7, -0.5, 0.0, 0.2, 0.5, 0.7, 1.0], ['<', '>']),
    ('body_pct', [0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9], ['<', '>']),
    ('atr_pct', [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55], ['<', '>']),
    ('dist_ema50', [-30, -20, -10, -5, 0, 3, 5, 7, 10, 15, 20], ['<', '>']),
    ('dist_ema200', [-60, -40, -20, 0, 15, 25, 40, 50, 60], ['<', '>']),
    ('upper_wick_pct', [0.02, 0.05, 0.08, 0.1, 0.15, 0.2, 0.3], ['<', '>']),
    ('lower_wick_pct', [0.05, 0.1, 0.12, 0.15, 0.2, 0.25, 0.3], ['<', '>']),
    ('range_atr_ratio', [0.8, 0.9, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5], ['<', '>']),
    ('hour', [1, 3, 5, 6, 7, 14, 15, 16, 17, 18], ['==', '!='])
]

def eval_cond(df_sub, f, val, op):
    if op == '<': return df_sub[f] < val
    if op == '>': return df_sub[f] > val
    if op == '==': return df_sub[f] == val
    if op == '!=': return df_sub[f] != val

valid_rules_sell = []

# 1-feature check
for f, vals, ops in features:
    for v in vals:
        for op in ops:
            c_win = eval_cond(sell_wins, f, v, op)
            if c_win.sum() == 0:
                c_loss = eval_cond(sell_losses, f, v, op)
                if c_loss.sum() >= 1:
                    valid_rules_sell.append((f"{f} {op} {v}", c_loss.sum(), c_loss))

# 2-feature check
for (f1, vals1, ops1), (f2, vals2, ops2) in itertools.combinations(features, 2):
    for v1 in vals1:
        for op1 in ops1:
            for v2 in vals2:
                for op2 in ops2:
                    c_win = eval_cond(sell_wins, f1, v1, op1) & eval_cond(sell_wins, f2, v2, op2)
                    if c_win.sum() == 0:
                        c_loss = eval_cond(sell_losses, f1, v1, op1) & eval_cond(sell_losses, f2, v2, op2)
                        if c_loss.sum() >= 2: # At least 2 losses blocked
                            valid_rules_sell.append((f"({f1} {op1} {v1}) & ({f2} {op2} {v2})", c_loss.sum(), c_loss))

valid_rules_sell.sort(key=lambda x: x[1], reverse=True)

print("\n--- TOP ZERO-WIN-LOSS-BLOCKING RULES FOR SELL (700 DAYS) ---")
for r, cnt, _ in valid_rules_sell[:25]:
    print(f"Blocks {cnt} losses | Rule: {r}")
    
# Greedy set cover for SELL
covered_losses = pd.Series(False, index=sell_losses.index)
selected_rules_sell = []

for r, cnt, c_loss in valid_rules_sell:
    new_covered = c_loss & (~covered_losses)
    if new_covered.sum() >= 1:
        selected_rules_sell.append((r, new_covered.sum()))
        covered_losses = covered_losses | c_loss
    if len(selected_rules_sell) >= 8 or covered_losses.sum() == len(sell_losses):
        break

print("\n--- GREEDY SELECTED SELL RULES (0 WINS BLOCKED) ---")
for r, new_cnt in selected_rules_sell:
    print(f"Adds +{new_cnt} losses blocked | Rule: {r}")
print(f"Total SELL losses blocked: {covered_losses.sum()} / {len(sell_losses)}")

# Now let's check BUY losses (there is only 1 BUY loss: 2025-05-09 04:00)
buy_wins = wins[wins['signal'] == 'BUY']
buy_losses = losses[losses['signal'] == 'BUY']

valid_rules_buy = []
for (f1, vals1, ops1), (f2, vals2, ops2) in itertools.combinations(features, 2):
    for v1 in vals1:
        for op1 in ops1:
            for v2 in vals2:
                for op2 in ops2:
                    c_win = eval_cond(buy_wins, f1, v1, op1) & eval_cond(buy_wins, f2, v2, op2)
                    if c_win.sum() == 0:
                        c_loss = eval_cond(buy_losses, f1, v1, op1) & eval_cond(buy_losses, f2, v2, op2)
                        if c_loss.sum() >= 1:
                            valid_rules_buy.append((f"({f1} {op1} {v1}) & ({f2} {op2} {v2})", c_loss.sum(), c_loss))

valid_rules_buy.sort(key=lambda x: x[1], reverse=True)
print("\n--- TOP ZERO-WIN-LOSS-BLOCKING RULES FOR BUY (700 DAYS) ---")
for r, cnt, _ in valid_rules_buy[:10]:
    print(f"Blocks {cnt} losses | Rule: {r}")
