import numpy as np
from scipy.optimize import linprog

def main():
    print("Loading data...")
    P = np.load('lts_P_matrix.npy')
    num_days, num_legs = P.shape
    
    # Target: We want extreme safety. Max historical daily loss allowed = - on  balance.
    # We will maximize the daily profit subject to this constraint.
    # We also cap max weight to 10.0 to prevent overfitting to a single 1-trade leg.
    c = -np.sum(P, axis=0) / num_days
    A_ub = -P
    b_ub = np.ones(num_days) * 500  # -P * w <= 500  => P * w >= -500
    bounds = [(0, 10.0) for _ in range(num_legs)]
    
    print("Optimizing for Maximum Safe Compounding Rate (Max DD <= 50%)...")
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
    
    if not res.success:
        print("Failed to find a safe combination.")
        return
        
    w_opt = res.x
    final_pnl = P @ w_opt
    
    avg_usd = final_pnl.mean()
    worst_usd = final_pnl.min()
    
    print(f"\n--- Base Simulation (Static ) ---")
    print(f"Optimal Base Avg PnL:  / day")
    print(f"Optimal Base Worst Day: ")
    
    # Calculate percentages relative to 1000
    avg_pct = avg_usd / 1000.0
    worst_pct = worst_usd / 1000.0
    
    print(f"\n--- Compounding Simulation (Target /day) ---")
    print(f"Daily Average Growth: {avg_pct*100:.2f}%")
    print(f"Max Daily Drawdown: {worst_pct*100:.2f}%")
    
    balance = 1000.0
    days_passed = 0
    
    # We simulate day by day. Assuming average growth, when do we hit 10k/day?
    # To hit 10k/day profit, with avg_pct growth, the balance needs to be 10000 / avg_pct
    target_profit = 10000.0
    target_balance = target_profit / avg_pct
    
    while balance < target_balance:
        days_passed += 1
        balance *= (1 + avg_pct)
        if days_passed > 10000: # safety break
            break
            
    print(f"Starting Balance: ,000")
    print(f"Days required to reach ,000/day profit: {days_passed} trading days")
    print(f"Account Balance at that point: ")
    
    # Also save the safe weights for the user
    import json
    with open("lts_leg_labels.json", "r") as f:
        labels = json.load(f)
        
    with open("lts_safe_compound_weights.txt", "w") as f:
        for i in range(num_legs):
            if w_opt[i] > 0.001:
                f.write(f"{labels[i]} : {w_opt[i]:.3f}\n")
    print("Saved safe weights to lts_safe_compound_weights.txt")

if __name__ == '__main__':
    main()
