import pandas as pd
import numpy as np

df = pd.read_csv('trade_features_18_deep.csv')
sells = df[df['type'] == 'SELL'].copy()

print(f"Total SELL trades: {len(sells)}, TP: {len(sells[sells['res']=='TP'])}, SL: {len(sells[sells['res']=='SL'])}")

feature_cols = [c for c in sells.columns if c not in ['time', 'type', 'res', 'pnl']]

X = sells[feature_cols].values
y = (sells['res'] == 'SL').values # 1 if SL, 0 if TP/BE/OPEN
is_tp = (sells['res'] == 'TP').values

best_rules = []
num_features = len(feature_cols)

# We want conditions of form: (X[:, i] > val1) & (X[:, j] > val2) -> predicts SL (so we block them)
# Let's test single feature rules first
for i in range(num_features):
    f_name = feature_cols[i]
    vals = np.unique(X[:, i])
    for val in vals:
        for op in ['>', '<', '>=', '<=']:
            if op == '>': cond = X[:, i] > val
            elif op == '<': cond = X[:, i] < val
            elif op == '>=': cond = X[:, i] >= val
            elif op == '<=': cond = X[:, i] <= val
            
            blocked_sl = np.sum(cond & (y == 1))
            blocked_tp = np.sum(cond & is_tp)
            
            if blocked_sl >= 4 and blocked_tp <= 1:
                best_rules.append({
                    'rule': f"{f_name} {op} {val:.4f}",
                    'blocked_sl': int(blocked_sl),
                    'blocked_tp': int(blocked_tp),
                    'score': int(blocked_sl * 10 - blocked_tp * 20)
                })

# Now test pairs of features
for i in range(num_features):
    for j in range(i+1, num_features):
        f1 = feature_cols[i]
        f2 = feature_cols[j]
        # sample percentiles to keep it fast
        vals1 = np.percentile(X[:, i], np.linspace(10, 90, 15))
        vals2 = np.percentile(X[:, j], np.linspace(10, 90, 15))
        for v1 in vals1:
            for op1 in ['>', '<']:
                c1 = (X[:, i] > v1) if op1 == '>' else (X[:, i] < v1)
                for v2 in vals2:
                    for op2 in ['>', '<']:
                        c2 = (X[:, j] > v2) if op2 == '>' else (X[:, j] < v2)
                        
                        cond = c1 & c2
                        blocked_sl = np.sum(cond & (y == 1))
                        blocked_tp = np.sum(cond & is_tp)
                        
                        if blocked_sl >= 5 and blocked_tp <= 1:
                            best_rules.append({
                                'rule': f"({f1} {op1} {v1:.4f}) and ({f2} {op2} {v2:.4f})",
                                'blocked_sl': int(blocked_sl),
                                'blocked_tp': int(blocked_tp),
                                'score': int(blocked_sl * 10 - blocked_tp * 20)
                            })

best_rules.sort(key=lambda x: (x['blocked_sl'], -x['blocked_tp']), reverse=True)
print("\nTop 20 SELL blocking rules:")
for r in best_rules[:20]:
    print(r)
