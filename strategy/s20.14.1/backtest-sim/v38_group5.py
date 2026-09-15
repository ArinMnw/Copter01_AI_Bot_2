import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from v38_engine import backtest_group_patterns

if __name__ == "__main__":
    print(f"Running Backtest for Group 5: Pattern: Fibo M30 + FVG D1 Group ✅ (Done)")
    
    target_orders = [6]
    
    target_tfs_config = {
        "Naiya": [],
        "Inst_Gap": [],
        "Fibo": ["M30"],
        "FVG": [],
        "GapSweep": [],
        "Doji": [],
        "MA12": []
    }
    
    backtest_group_patterns(days=365, compound=0.1, group_id=5, target_orders=target_orders, target_tfs_config=target_tfs_config)
