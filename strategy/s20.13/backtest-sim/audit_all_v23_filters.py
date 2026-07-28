import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from strategy20_13_23 import compute_indicators_df, evaluate_bar
import config

def audit_all_filters(days=700, symbol="XAUUSD.iux", compound=1.5):
    path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
    if not mt5.initialize(path=path): return
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start_time, end_time)
    
    df_master = compute_indicators_df(rates)
    df_master['upper_wick'] = df_master['high'] - np.maximum(df_master['open'], df_master['close'])
    df_master['lower_wick'] = np.minimum(df_master['open'], df_master['close']) - df_master['low']
    df_master['upper_wick_pct'] = df_master['upper_wick'] / (df_master['range'] + 0.0001)
    df_master['lower_wick_pct'] = df_master['lower_wick'] / (df_master['range'] + 0.0001)
    df_master['dist_ema50'] = df_master['close'] - df_master['ema_50']
    df_master['dist_ema200'] = df_master['close'] - df_master['ema_200']
    df_master['hour'] = df_master['time_dt'].dt.hour

    # Let's inspect the reasons returned when signal == "WAIT" in evaluate_bar!
    # Let's collect every single WAIT reason returned across the 700 days when a PA signal (BUY or SELL) was actually present!
    
    blocked_setups = []
    for i in range(100, len(rates) - 10):
        # Let's see if there was a PA structure
        recent_3 = df_master.iloc[i-2:i+1]
        prev_bar = df_master.iloc[i-1]
        cur = df_master.iloc[i]
        
        # BUY structure check
        local_low = recent_3['low'].min()
        sweep_buy = recent_3['low'].min() < local_low # wait, how does evaluate_bar check sweep?
        # Instead of recreating PA logic, let's look at evaluate_bar reasons!
        res = evaluate_bar(df_master, i, tf="H1")
        if res and res.get("signal") == "WAIT" and "Block" in res.get("reason", ""):
            blocked_setups.append({"index": i, "reason": res["reason"].split(" (")[0], "full_reason": res["reason"]})
            
    df_blocked = pd.DataFrame(blocked_setups)
    if len(df_blocked) > 0:
        print("================== BLOCKED SETUPS BY FILTER IN V23 ==================")
        print(df_blocked['reason'].value_counts())
    
    mt5.shutdown()

if __name__ == "__main__":
    audit_all_filters()
