import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import sys
from datetime import datetime, timedelta

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

sym = "XAUUSD.iux"

# Get data from 2026-07-22 15:00 (Server time) to now
start = datetime(2026, 7, 22, 10, 0)
rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 100)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

# Find the exact bar of the setup: 2026-07-22 15:00
# Actually let's just re-calculate the ATR and TPs at that specific bar
high_low = df['high'] - df['low']
high_close = np.abs(df['high'] - df['close'].shift())
low_close = np.abs(df['low'] - df['close'].shift())
tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
df['atr'] = tr.rolling(window=14).mean()

setup_bar = None
setup_idx = -1
for i in range(15, len(df)):
    if df.iloc[i]['time'] == datetime(2026, 7, 22, 15, 0):
        setup_bar = df.iloc[i]
        setup_idx = i
        break

if setup_bar is None:
    print("Could not find the setup bar.")
    mt5.shutdown()
    sys.exit()

# Reconstruct the Sweep High
lookback_bars = df.iloc[setup_idx-3:setup_idx]
local_high = lookback_bars['high'].max()

entry_price = setup_bar['close']
atr = setup_bar['atr']
fuel_multiplier_d1 = np.sqrt(1440 / 60) # 4.898979

tp_15 = local_high - (atr * 1.5 * fuel_multiplier_d1)
tp_20 = local_high - (atr * 2.0 * fuel_multiplier_d1)
tp_26 = local_high - (atr * 2.6 * fuel_multiplier_d1)

# Check lowest price reached AFTER the entry
future_bars = df.iloc[setup_idx+1:]
lowest_reached = future_bars['low'].min()
lowest_time = future_bars.loc[future_bars['low'].idxmin(), 'time']

print(f"Entry Price: {entry_price:.2f} (Time: {setup_bar['time']})")
print(f"Sweep High (Base): {local_high:.2f}")
print(f"ATR: {atr:.2f}")
print(f"Fuel Multiplier (D1): {fuel_multiplier_d1:.3f}")
print("-" * 30)
print(f"Target SD 1.5: {tp_15:.2f}")
print(f"Target SD 2.0: {tp_20:.2f}")
print(f"Target SD 2.6: {tp_26:.2f}")
print("-" * 30)
print(f"Lowest Price Reached: {lowest_reached:.2f} (at {lowest_time})")

if lowest_reached <= tp_15:
    print("✅ Hit SD 1.5")
else:
    print("❌ Missed SD 1.5")
    
if lowest_reached <= tp_20:
    print("✅ Hit SD 2.0")
else:
    print("❌ Missed SD 2.0")

if lowest_reached <= tp_26:
    print("✅ Hit SD 2.6")
else:
    print("❌ Missed SD 2.6")

mt5.shutdown()
