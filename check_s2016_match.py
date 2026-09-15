import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
import importlib.util

sys.path.append('d:/Project/Copter01_AI_Bot_2')

spec = importlib.util.spec_from_file_location("strategy20_16", "d:/Project/Copter01_AI_Bot_2/strategy/s20.16/strategy20_16.py")
strategy20_16 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strategy20_16)

import config
config.S20_16_TPSL_MODE = "S20.14.23"

mt5.initialize()

tf = mt5.TIMEFRAME_M1
rates = mt5.copy_rates_from_pos("XAUUSD.iux", tf, 0, 1500)
if rates is None:
    print("Could not get rates. Make sure symbol is correct.")
    mt5.shutdown()
    sys.exit()
    
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

print("--- Backtest Latest Signals (Last 1500 mins) ---")
df_master = strategy20_16.compute_indicators_df(rates)

for i in range(100, len(rates) - 1):
    res = strategy20_16.evaluate_bar(df_master, i, tf="M1")
    if res and res.get("signal") in ["BUY", "SELL"]:
        print(f"Time: {df['time'].iloc[i]}, Sig: {res.get('signal')}, Entry: {res.get('entry')}, SL: {res.get('sl')}, TP: {res.get('tp')}")

mt5.shutdown()
