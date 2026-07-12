import numpy as np
import json
import os
import argparse
from scipy.optimize import linprog

def optimize_for_target(P, target_avg, cap, min_worst_day, min_weight):
    num_days, num_legs = P.shape
    
    c = np.zeros(num_legs + 1)
    c[-1] = -1.0 # minimize -M -> maximize M
    
    A_ub1 = np.zeros((num_days, num_legs + 1))
    A_ub1[:, :num_legs] = -P
    A_ub1[:, -1] = 1.0
    b_ub1 = np.zeros(num_days)
    
    A_ub2 = np.zeros((1, num_legs + 1))
    A_ub2[0, :num_legs] = -np.sum(P, axis=0)
    b_ub2 = np.array([-target_avg * num_days])
    
    A_ub = np.vstack([A_ub1, A_ub2])
    b_ub = np.concatenate([b_ub1, b_ub2])
    
    bounds = [(min_weight, cap) for _ in range(num_legs)]
    bounds.append((None, None))
    
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
    return res

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cap", type=float, default=1200.0, help="Maximum weight for a single leg")
    parser.add_argument("--min-worst-day", type=float, default=-1.0, help="Minimum worst day allowed (e.g., 0 for no loss, -50000 for high risk)")
    parser.add_argument("--min-weight", type=float, default=0.0, help="Minimum weight for a single leg (forces all legs to trade)")
    parser.add_argument("--out", type=str, default="lts_avengers_p34_weights.txt", help="Output filename")
    args = parser.parse_args()
    
    print("Loading extended matrix...")
    try:
        P_raw = np.load("lts_P_matrix_ext.npy")
        with open("lts_leg_labels_ext.json", "r") as f:
            labels = json.load(f)
    except FileNotFoundError:
        print("Extended matrix not found.")
        return
        
    print(f"Matrix loaded. Shape: {P_raw.shape}")
    print(f"Constraints: Cap={args.cap}, MinWorstDay={args.min_worst_day}, MinWeight={args.min_weight}")
    
    # ---------------------------------------------------------
    # APPLY PHASE 3 & 4 HEURISTIC TO P MATRIX
    # Phase 3 (Wins): +20%
    # Phase 4 (Losses): Cut by 15% combined with dynamic lot scale back (0.80) -> 0.80 * 0.85 = 0.68
    # ---------------------------------------------------------
    print("Applying Phase 3 & 4 heuristics to leg daily vectors...")
    P = np.where(P_raw > 0, P_raw * 1.20, P_raw * 0.68)
    
    num_days, num_legs = P.shape
    
    # Binary search for max target_avg
    low = 1000.0
    high = 85000.0
    if args.cap > 1200.0:
        high = 200000.0 # for high risk
    if args.min_weight > 0:
        low = -50000.0 # if forcing min weight, avg could be negative
        
    best_res = None
    best_target = low
    best_w = None
    
    print(f"Starting binary search for highest Avg $/day with Worst Day >= {args.min_worst_day}...")
    
    for _ in range(15): # 15 iterations should give ~0.5 precision
        mid = (low + high) / 2.0
        print(f"Testing Target Avg: {mid:.2f}...")
        res = optimize_for_target(P, mid, args.cap, args.min_worst_day, args.min_weight)
        
        if res.success and res.x[-1] >= args.min_worst_day - 1.0: # M >= target (allow tiny float error)
            print(f" -> SUCCESS! Worst Day: {res.x[-1]:.2f}")
            best_res = res
            best_target = mid
            best_w = res.x[:num_legs]
            low = mid
        else:
            if res.success:
                print(f" -> FAILED (Worst Day = {res.x[-1]:.2f} < {args.min_worst_day})")
            else:
                print(" -> FAILED (No feasible solution)")
            high = mid
            
    if best_w is not None:
        print(f"\nOptimization Complete!")
        print(f"Best Achievable Avg $/day: {best_target:.2f}")
        
        final_pnl = P @ best_w
        print(f"Final Worst day: {final_pnl.min():.2f}")
        
        weights_file = os.path.join("strategy", "lts", "optimized_weights", args.out)
        with open(weights_file, "w") as f:
            for i in range(num_legs):
                if best_w[i] > 1e-4:
                    f.write(f"{labels[i]} : {best_w[i]:.3f}\n")
        print(f"Saved {weights_file}")
    else:
        print(f"Could not find any solution with Worst Day >= {args.min_worst_day}")

if __name__ == "__main__":
    main()
