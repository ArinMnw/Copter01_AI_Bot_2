import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from v38_engine import backtest_group_patterns

if __name__ == "__main__":
    print(f"Running Backtest for Group 9: Pattern: นัยยะ H1 + Doji H1")
    
    target_orders = [11]
    
    target_tfs_config = {
        "Naiya": ["H1"],
        "Inst_Gap": [],
        "Fibo": [],
        "FVG": [],
        "GapSweep": [],
        "Doji": ["H1"],
        "MA12": []
    }
    
    backtest_group_patterns(days=365, compound=0.1, group_id=9, target_orders=target_orders, target_tfs_config=target_tfs_config)
