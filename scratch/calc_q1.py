import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import sys
from datetime import datetime

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

sym = "XAUUSD.iux"
rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 500)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

high_low = df['high'] - df['low']
high_close = np.abs(df['high'] - df['close'].shift())
low_close = np.abs(df['low'] - df['close'].shift())
tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
df['atr'] = tr.rolling(window=14).mean()

# Check ATR at July 9 19:00
target_bar = df[df['time'] == '2026-07-09 19:00:00']
if not target_bar.empty:
    atr = target_bar['atr'].values[0]
    fuel_multiplier = np.sqrt(1440/60) # D1 = 4.898979
    fuel = atr * 2.6 * fuel_multiplier
    base = 4138.08
    tp = base - fuel
    print(f"ATR at 19:00: {atr:.3f}")
    print(f"Fuel Multiplier: {fuel_multiplier:.3f}")
    print(f"Fuel: {fuel:.3f}")
    print(f"TP: {tp:.3f}")

mt5.shutdown()
