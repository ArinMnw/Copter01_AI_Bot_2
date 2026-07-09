import numpy as np
import json
from scipy.optimize import linprog

def optimize_for_target(P, target_avg):
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
    
    bounds = [(0, 1200.0) for _ in range(num_legs)]
    bounds.append((None, None))
    
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
    return res

def main():
    print("Loading extended matrix...")
    try:
        P = np.load("lts_P_matrix_ext.npy")
        with open("lts_leg_labels_ext.json", "r") as f:
            labels = json.load(f)
    except FileNotFoundError:
        print("Extended matrix not found. Waiting for add_s9x_to_matrix.py to finish.")
        return
        
    num_days, num_legs = P.shape
    print(f"Matrix loaded. Shape: {P.shape}")
    
    # Binary search for max target_avg
    low = 10000.0
    high = 25000.0
    best_res = None
    best_target = 0
    best_w = None
    
    print("Starting binary search for highest Avg $/day with Worst Day >= 0...")
    
    for _ in range(15): # 15 iterations should give ~0.5 precision
        mid = (low + high) / 2.0
        print(f"Testing Target Avg: {mid:.2f}...")
        res = optimize_for_target(P, mid)
        
        if res.success and res.x[-1] >= -1.0: # M >= 0 (allow tiny float error)
            print(f" -> SUCCESS! Worst Day: {res.x[-1]:.2f}")
            best_res = res
            best_target = mid
            best_w = res.x[:num_legs]
            low = mid
        else:
            if res.success:
                print(f" -> FAILED (Worst Day = {res.x[-1]:.2f} < 0)")
            else:
                print(" -> FAILED (No feasible solution)")
            high = mid
            
    if best_w is not None:
        print(f"\nOptimization Complete!")
        print(f"Best Achievable Avg $/day: {best_target:.2f}")
        
        final_pnl = P @ best_w
        print(f"Final Worst day: {final_pnl.min():.2f}")
        
        import os
        weights_file = os.path.join("strategy", "lts", "optimized_weights", "lts_optimized_weights.txt")
        with open(weights_file, "w") as f:
            for i in range(num_legs):
                if best_w[i] > 1e-4:
                    f.write(f"{labels[i]} : {best_w[i]:.3f}\n")
        print("Saved lts999_optimized_weights.txt")
        
        # Check if S95/S96/S97 were selected
        s9x_count = 0
        for i in range(num_legs):
            if best_w[i] > 1e-4 and ("S95" in labels[i] or "S96" in labels[i] or "S97" in labels[i]):
                s9x_count += 1
                print(f"Selected new leg: {labels[i]} with weight {best_w[i]:.3f}")
                
        print(f"Total S9x legs selected: {s9x_count}")
    else:
        print("Could not find any solution with Worst Day >= 0 and Target >= 10000")

if __name__ == "__main__":
    main()
