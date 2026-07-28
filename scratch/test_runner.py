import MetaTrader5 as mt5
import pandas as pd
import sys, os
from datetime import datetime, timedelta

sys.path.append(os.path.abspath('d:\\Project\\Copter01_AI_Bot_2\\strategy\\s20.13'))
sys.path.append(os.path.abspath('d:\\Project\\Copter01_AI_Bot_2'))
from strategy20_13 import strategy_20_13

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

symbol = "XAUUSD.iux"
now = datetime.now()
start = now - timedelta(days=30)
rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start, now)

found = 0
for i in range(100, len(rates) - 1):
    slice_rates = rates[:i]
    res = strategy_20_13(slice_rates, tf="H1")
    if res.get("signal") in ["BUY", "SELL"]:
        print(f"[{datetime.fromtimestamp(rates[i-1]['time'])}] {res}")
        found += 1

print(f"Found {found} trades.")
mt5.shutdown()
