import numpy as np
import json
import argparse
from scipy.optimize import linprog

def optimize_for_compounding(P, labels, max_dd_usd=500.0, max_weight=10.0, target_profit=10000.0, base_balance=1000.0):
    num_days, num_legs = P.shape
    
    # Maximize the daily average profit -> Minimize -average
    c = -np.sum(P, axis=0) / num_days
    
    # Constraint: max daily loss <= max_dd_usd
    A_ub1 = -P
    b_ub1 = np.ones(num_days) * max_dd_usd
    
    # Constraint: sum of weights <= max_total_weight (300 = 3 lots total max)
    A_ub2 = np.ones((1, num_legs))
    b_ub2 = np.array([300.0])
    
    A_ub = np.vstack([A_ub1, A_ub2])
    b_ub = np.concatenate([b_ub1, b_ub2])
    
    bounds = [(0, max_weight) for _ in range(num_legs)]
    
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
    
    if not res.success:
        print(f"Failed to find a safe combination for {num_legs} legs.")
        return
        
    w_opt = res.x
    final_pnl = P @ w_opt
    
    avg_usd = final_pnl.mean()
    worst_usd = final_pnl.min()
    
    avg_pct = avg_usd / base_balance
    worst_pct = worst_usd / base_balance
    
    print(f"--- LTS {num_legs} Compounding Simulation ---")
    print(f"Optimal Base Avg PnL: ${avg_usd:.2f} / day")
    print(f"Optimal Base Worst Day: ${worst_usd:.2f}")
    print(f"Daily Average Growth: {avg_pct*100:.2f}%")
    print(f"Max Daily Drawdown: {worst_pct*100:.2f}%\n")
    
    balance = base_balance
    days_passed = 0
    target_balance = target_profit / avg_pct if avg_pct > 0 else float('inf')
    
    # Check if we can reach target in 30 days
    test_days = [7, 15, 21, 30]
    balances_at_days = {}
    
    while balance < target_balance:
        days_passed += 1
        balance *= (1 + avg_pct)
        if days_passed in test_days:
            balances_at_days[days_passed] = balance
            
        if days_passed > 10000:
            print("Took more than 10,000 days. Stopping.")
            break
            
    print(f"Result:")
    print(f"- Starting Balance: ${base_balance:,.2f}")
    for d in test_days:
        b = balances_at_days.get(d, target_balance) # if reached earlier
        prof = b * avg_pct
        print(f"  Day {d}: Balance ${b:,.2f} -> Daily Profit: ${prof:,.2f}")
        
    print(f"- Target Reached: {days_passed} trading days to reach ${target_profit:,.2f}/day profit.")
    print(f"- Account Balance at target: ${balance:,.2f}\n")
    
    # Save optimized weights
    with open(f"lts{num_legs}_safe_compound_weights.txt", "w") as f:
        for i in range(num_legs):
            if w_opt[i] > 0.001:
                f.write(f"{labels[i]} : {w_opt[i]:.3f}\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", default="lts_P_matrix.npy")
    parser.add_argument("--labels", default="lts_leg_labels.json")
    args = parser.parse_args()
    
    print("Loading data...")
    try:
        P = np.load(args.matrix)
        with open(args.labels, "r") as f:
            labels = json.load(f)
    except Exception as e:
        print(f"Error loading data: {e}")
        return
        
    total_legs = P.shape[1]
    
    # We want to test LTS 44, LTS 71, and LTS MAX
    test_legs = [44, 71, total_legs]
    
    for n in test_legs:
        if n > total_legs:
            continue
        print(f"\n======================================")
        optimize_for_compounding(P[:, :n], labels[:n], max_dd_usd=500.0, max_weight=50.0, target_profit=10000.0, base_balance=1000.0)

if __name__ == '__main__':
    main()
