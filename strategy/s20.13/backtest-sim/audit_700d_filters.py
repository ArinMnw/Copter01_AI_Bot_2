import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from strategy20_13_22 import compute_indicators_df, evaluate_bar

def audit_filters(days=700, symbol="XAUUSD.iux"):
    path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
    if not mt5.initialize(path=path): return
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start_time, end_time)
    
    df_master = compute_indicators_df(rates)
    
    # Let's see all bars where Engulfing + Sweep happens!
    raw_setups = 0
    reasons_count = {}
    
    for i in range(100, len(rates) - 10):
        res = evaluate_bar(df_master, i, tf="H1")
        reason = res.get("reason", "")
        if "Block" in reason or "Trap" in reason or "too low" in reason or "too high" in reason:
            reasons_count[reason] = reasons_count.get(reason, 0) + 1
            
    print(f"--- FILTER BLOCK COUNTS OVER {days} DAYS ---")
    sorted_reasons = sorted(reasons_count.items(), key=lambda x: x[1], reverse=True)
    for r, cnt in sorted_reasons[:30]:
        print(f"{cnt:3d} blocks | {r}")
        
    mt5.shutdown()

if __name__ == "__main__":
    audit_filters()
