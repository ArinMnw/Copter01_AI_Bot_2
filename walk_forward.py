import json
import itertools
import os
from datetime import datetime

# You would import your existing simulation scripts here
# import sim_s1_backtest

OPTIMIZED_PARAMS_FILE = "optimized_params.json"

def run_optimization():
    print("Starting Walk-Forward Optimization...")
    
    # ── Auto-Retrain ML Model ──
    print("\n[1/2] Auto-Retraining ML Model from MT5 History...")
    try:
        import ml_scoring
        ml_scoring.train_from_mt5_history(days=30)
    except ImportError:
        print("ml_scoring.py not found or not configured.")
        
    print("\n[2/2] Running Parameter Optimization...")
    # Define parameter grid
    # Define parameter grid
    param_grid = {
        "SL_ATR_MULT": [1, 2, 3],
        "S1_ZONE_MODE": ["normal", "zone", "swing"],
        "NEWS_FILTER_ENABLED": [True, False],
        "ML_PROB_THRESHOLD": [0.40, 0.45, 0.50]
    }
    
    keys, values = zip(*param_grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    best_params = None
    best_profit = -float('inf')
    
    print(f"Testing {len(combinations)} parameter combinations...")
    
    for i, params in enumerate(combinations):
        # In a real scenario, you would pass these params to your backtest module:
        # result = sim_s1_backtest.run_backtest(params)
        # For demonstration, we simulate a profit result based on random/mock logic
        
        # Mock logic: "swing" is usually better, smaller SL might hit often but we'll mock it
        mock_profit = 1000 
        if params["S1_ZONE_MODE"] == "swing": mock_profit += 500
        if params["SL_ATR_MULT"] == 2: mock_profit += 200
        if params["NEWS_FILTER_ENABLED"]: mock_profit += 300
        
        # print(f"[{i+1}/{len(combinations)}] Tested {params} -> Profit: ${mock_profit:.2f}")
        
        if mock_profit > best_profit:
            best_profit = mock_profit
            best_params = params
            
    print("\nOptimization Complete!")
    print(f"Best Profit: ${best_profit:.2f}")
    print(f"Best Parameters: {best_params}")
    
    best_params["last_optimized"] = datetime.now().isoformat()
    
    with open(OPTIMIZED_PARAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(best_params, f, indent=4)
        
    print(f"Saved optimized parameters to {OPTIMIZED_PARAMS_FILE}")

if __name__ == "__main__":
    run_optimization()
