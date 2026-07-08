import numpy as np
import json
from scipy.optimize import linprog

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-avg", type=float, default=10000.0, help="Target average PnL per day")
    args = parser.parse_args()
    
    print("Loading data...")
    P = np.load("lts_P_matrix.npy") # shape: (550, num_legs)
    W_orig = np.load("lts_W_orig.npy") # shape: (num_legs,)
    with open("lts_leg_labels.json", "r") as f:
        labels = json.load(f)
        
    num_days, num_legs = P.shape
    print(f"Loaded matrix: {num_days} days, {num_legs} legs.")
    
    # We want to find w >= 0 to:
    # Maximize M (floor)
    # subject to:
    # 1) P * w >= M * ones  =>  -P * w + M * ones <= 0
    # 2) sum(P * w) / 550 >= target_avg => -sum(P) * w <= -target_avg * 550
    # 3) 0 <= w_j <= 1200
    
    # Let x = [w_1, w_2, ..., w_N, M]
    # We want to minimize -M
    c = np.zeros(num_legs + 1)
    c[-1] = -1.0 # minimize -M
    
    # Constraint 1: -P * w + M <= 0
    A_ub1 = np.zeros((num_days, num_legs + 1))
    A_ub1[:, :num_legs] = -P
    A_ub1[:, -1] = 1.0
    b_ub1 = np.zeros(num_days)
    
    # Constraint 2: -sum(P, axis=0) * w <= -target_avg * 550
    A_ub2 = np.zeros((1, num_legs + 1))
    A_ub2[0, :num_legs] = -np.sum(P, axis=0)
    b_ub2 = np.array([-args.target_avg * num_days])
    
    A_ub = np.vstack([A_ub1, A_ub2])
    b_ub = np.concatenate([b_ub1, b_ub2])
    
    # Bounds
    bounds = []
    for i in range(num_legs):
        # We cap weights at 1200 to prevent extreme scaling, similar to original auto-ladder cap.
        bounds.append((0, 1200.0))
    # Bound for M
    bounds.append((None, None)) # M can be anything, though it will be negative
    
    print("Running Linear Programming Solver (HiGHS)...")
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
    
    if res.success:
        print("Optimization Successful!")
        w_opt = res.x[:num_legs]
        M_opt = res.x[-1]
        
        final_pnl = P @ w_opt
        
        print(f"Original Avg $/day: {(P @ W_orig).mean():.2f}")
        print(f"Original Worst day: {(P @ W_orig).min():.2f}")
        print(f"Optimized Avg $/day: {final_pnl.mean():.2f}")
        print(f"Optimized Worst day: {final_pnl.min():.2f}")
        
        # Save optimized weights
        np.save("lts_W_opt.npy", w_opt)
        
        # Write out to a new log-like format or CSV
        with open("lts_optimized_weights.txt", "w") as f:
            for i in range(num_legs):
                f.write(f"{labels[i]} : {w_opt[i]:.3f}\n")
        print("Saved lts_W_opt.npy and lts_optimized_weights.txt")
    else:
        print("Optimization failed:", res.message)

if __name__ == "__main__":
    main()
