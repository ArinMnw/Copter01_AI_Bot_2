import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
import sys

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

sym = "XAUUSD.iux"
# Get H1 bars up to July 23
rates_h1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 500)
df_h1 = pd.DataFrame(rates_h1)
df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
tr = pd.concat([df_h1['high'] - df_h1['low'], 
               (df_h1['high'] - df_h1['close'].shift()).abs(), 
               (df_h1['low'] - df_h1['close'].shift()).abs()], axis=1).max(axis=1)
df_h1['atr'] = tr.rolling(14).mean()

# Get H12 bars up to July 23
rates_h12 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H12, 0, 100)
df_h12 = pd.DataFrame(rates_h12)
df_h12['time'] = pd.to_datetime(df_h12['time'], unit='s')
tr12 = pd.concat([df_h12['high'] - df_h12['low'], 
                 (df_h12['high'] - df_h12['close'].shift()).abs(), 
                 (df_h12['low'] - df_h12['close'].shift()).abs()], axis=1).max(axis=1)
df_h12['atr'] = tr12.rolling(14).mean()

# Print recent
print("Recent H1 ATR:")
print(df_h1.tail(10)[['time', 'atr']])
print("\nRecent H12 ATR:")
print(df_h12.tail(5)[['time', 'atr']])

mt5.shutdown()
