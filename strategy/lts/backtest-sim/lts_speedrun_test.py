import numpy as np
import math
from scipy.optimize import linprog

P = np.load('lts_P_matrix.npy')
num_days, num_legs = P.shape

# We want to find the MAX possible return with Worst Day >= -950
c = -np.sum(P, axis=0) / num_days
A_ub = -P
b_ub = np.ones(num_days) * 950

best_days = 99999
best_w = None
best_g = 0

for max_w in [10, 20, 50, 100, 200, 500]:
    bounds = [(0, max_w) for _ in range(num_legs)]
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
    if res.success:
        avg_pnl = -res.fun
        g = avg_pnl / 1000.0
        if g > 0:
            try:
                days = math.log(10.0 / g) / math.log(1 + g)
                print(f"Max Weight {max_w:3d} => Avg PnL:  (g={g*100:5.2f}%) => Days to 10k/day: {days:.1f}")
                if days < best_days:
                    best_days = days
                    best_w = res.x
                    best_g = g
            except Exception as e:
                pass

if best_w is not None:
    # Save the fastest safe weights
    np.save("lts_fastest_weights.npy", best_w)
    import json
    with open('lts_leg_labels.json', 'r') as f:
        labels = json.load(f)
    with open('lts_fastest_weights.txt', 'w') as f:
        for i in range(num_legs):
            if best_w[i] > 0.001:
                f.write(f'{labels[i]} : {best_w[i]:.3f}\n')
