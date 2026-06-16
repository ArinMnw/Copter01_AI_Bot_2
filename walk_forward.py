import json
import itertools
import os
from datetime import datetime

# You would import your existing simulation scripts here
# import sim_s1_backtest

OPTIMIZED_PARAMS_FILE = "optimized_params.json"

def run_optimization():
    print("Starting Walk-Forward Optimization...")
    
    # ── 1. Auto-Retrain ML Model ──
    # อ่านจาก MT5 History ย้อนหลัง 30 วันตายตัว
    print("\n[1/2] Auto-Retraining ML Model from MT5 History (Fixed 30 Days)...")
    try:
        import ml_scoring
        ml_scoring.train_from_mt5_history(days=30)
    except ImportError:
        print("ml_scoring.py not found or not configured.")
        
    # ── 2. Walk-Forward Parameter Optimization ──
    # ใช้ OHLC ย้อนหลัง 30 วันตายตัว
    now = datetime.now()
    start_dt = now - __import__('datetime').timedelta(days=30)
    start_str = start_dt.strftime("%Y-%m-%d %H:%M")
    end_str = now.strftime("%Y-%m-%d %H:%M")

    print(f"\n[2/2] Running Parameter Optimization ({start_str} to {end_str})...")
    
    # Define parameter grid
    param_grid = {
        "SL_ATR_MULT": [1, 2],
        "ML_PROB_THRESHOLD": [0.45, 0.50]
    }
    
    keys, values = zip(*param_grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    best_params = None
    best_profit = -float('inf')
    
    print(f"Testing {len(combinations)} parameter combinations...")
    
    import subprocess
    import re
    
    for i, params in enumerate(combinations):
        # 1. Temporarily write params to let config.py pick it up
        with open(OPTIMIZED_PARAMS_FILE, "w", encoding="utf-8") as f:
            json.dump(params, f, indent=4)
            
        # 2. Run backtest engine (Using S14 for speed in optimization, or 'all')
        print(f"[{i+1}/{len(combinations)}] Testing {params}... ", end="", flush=True)
        
        cmd = [
            "python", "backtest_auto_trade.py",
            "--start", start_str,
            "--end", end_str,
            "--strategies", "14"  # Defaulting to 14 for reasonable optimization time
        ]
        
        try:
            # We set PYTHONIOENCODING just in case
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            
            proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
            
            # Parse output for "GRAND TOTAL: X USD"
            match = re.search(r"GRAND TOTAL:\s*([-\d\.]+)\s*USD", proc.stdout)
            if match:
                profit = float(match.group(1))
            else:
                profit = -float('inf')
                
            print(f"Profit: ${profit:.2f}")
            
            if profit > best_profit:
                best_profit = profit
                best_params = params
        except Exception as e:
            print(f"Error: {e}")
            
    print("\nOptimization Complete!")
    print(f"Best Profit: ${best_profit:.2f}")
    if best_params:
        print(f"Best Parameters: {best_params}")
    else:
        best_params = combinations[0]
        
    best_params["last_optimized"] = datetime.now().isoformat()
    
    with open(OPTIMIZED_PARAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(best_params, f, indent=4)
        
    print(f"Saved optimized parameters to {OPTIMIZED_PARAMS_FILE}")

if __name__ == "__main__":
    run_optimization()
