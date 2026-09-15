import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from v38_engine import backtest_group_patterns

if __name__ == "__main__":
    print(f"Running Backtest for Group 3: Pattern: Fibo H1 + Div H1 Group ✅ (Done)")
    
    target_orders = [3]
    
    target_tfs_config = {
        "Naiya": ["H1", "H12", "D1"],
        "Inst_Gap": ["M15", "M30", "H1"],
        "Fibo": ["M15", "M30", "H1"],
        "FVG": ["H1", "H12", "D1"],
        "GapSweep": ["H1", "H4", "D1"],
        "Doji": ["H1"],
        "MA12": ["H1"]
    }
    
    backtest_group_patterns(days=365, compound=0.1, group_id=3, target_orders=target_orders, target_tfs_config=target_tfs_config)
