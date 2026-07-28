import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
import itertools

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from strategy20_13_22 import compute_indicators_df, evaluate_bar, get_fuel_multiplier
import config

def search_150k(days=700, symbol="XAUUSD.iux", compound=1.5):
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

    # Let's see: what if we evaluate bars without some of the restrictive older SELL filters?
    # Let's check which older SELL filters in evaluate_bar block the most WINNING trades!
    
    # Let's define a clean base evaluator that tests removing individual older SELL filters
    signals_base = []
    for i in range(100, len(rates) - 10):
        res = evaluate_bar(df_master, i, tf="H1")
        if res and res.get("signal") in ["BUY", "SELL"]:
            signals_base.append((i, res["signal"], res["entry"], res["sl"], res["tp"], df_master.iloc[i]))

    print(f"Total base signals with v22 filters: {len(signals_base)}")
    
    # Now let's check: what if we relax ONE v20 or v21 SELL filter in evaluate_bar that might be too strict on 700 days?
    # Let's see all SELL filters in evaluate_bar by inspecting which ones blocked setups when we ran audit!
    mt5.shutdown()

if __name__ == "__main__":
    search_150k()
