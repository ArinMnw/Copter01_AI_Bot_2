import pandas as pd
import numpy as np
import itertools

df = pd.read_csv('v20_all_trades_features.csv')
wins = df[df['outcome'] == 'WIN']
losses = df[df['outcome'] == 'LOSS']

print(f"Searching precision rules on {len(losses)} losses without touching {len(wins)} wins...")

# Let's test combinations of 2 features for SELL
sell_wins = wins[wins['signal'] == 'SELL']
sell_losses = losses[losses['signal'] == 'SELL']

# Let's define simple thresholds for each feature to test combinations
features = [
    ('rsi', [30, 35, 40, 45, 50, 55, 60], ['<', '>']),
    ('rsi_7', [25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75], ['<', '>']),
    ('adx', [20, 25, 30, 35, 40, 45, 50, 60], ['<', '>']),
    ('di_diff', [-30, -20, -10, -5, 0, 5, 8, 10, 12], ['<', '>']),
    ('vol_ratio', [0.5, 0.8, 1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0], ['<', '>']),
    ('z_score', [-3.0, -2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0], ['<', '>']),
    ('body_pct', [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], ['<', '>']),
    ('atr_pct', [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6], ['<', '>']),
    ('dist_ema50', [-50, -30, -20, -10, 0, 10, 20, 30, 40], ['<', '>']),
    ('upper_wick_pct', [0.05, 0.1, 0.15, 0.2, 0.25, 0.3], ['<', '>']),
    ('lower_wick_pct', [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5], ['<', '>']),
    ('hour', [3, 5, 6, 10, 15, 16, 17, 19, 21], ['==', '!='])
]

# Generate all 1-feature and 2-feature conditions
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
            if c_win.sum() == 0: # 0 wins blocked!
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

# Sort by losses blocked
valid_rules_sell.sort(key=lambda x: x[1], reverse=True)

print("\n--- TOP ZERO-WIN-LOSS-BLOCKING RULES FOR SELL ---")
for r, cnt, _ in valid_rules_sell[:30]:
    print(f"Blocks {cnt} losses | Rule: {r}")
    
# Let's do a greedy set cover to find a set of 5-6 rules that block the maximum number of SELL losses!
covered_losses = pd.Series(False, index=sell_losses.index)
selected_rules_sell = []

for r, cnt, c_loss in valid_rules_sell:
    new_covered = c_loss & (~covered_losses)
    if new_covered.sum() >= 2: # Must add at least 2 new losses
        selected_rules_sell.append((r, new_covered.sum()))
        covered_losses = covered_losses | c_loss
    if covered_losses.sum() >= 14:
        break

print("\n--- GREEDY SELECTED SELL RULES (0 WINS BLOCKED) ---")
for r, new_cnt in selected_rules_sell:
    print(f"Adds +{new_cnt} losses blocked | Rule: {r}")
print(f"Total SELL losses blocked: {covered_losses.sum()} / {len(sell_losses)}")

# Now let's check BUY losses
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
print("\n--- TOP ZERO-WIN-LOSS-BLOCKING RULES FOR BUY ---")
for r, cnt, _ in valid_rules_buy[:15]:
    print(f"Blocks {cnt} losses | Rule: {r}")
