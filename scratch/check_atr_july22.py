import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
import sys

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

sym = "XAUUSD.iux"
target_dt = datetime.strptime("2026-07-22 13:00", "%Y-%m-%d %H:%M")

rates = mt5.copy_rates_from(sym, mt5.TIMEFRAME_H1, target_dt, 30)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

high_low = df['high'] - df['low']
high_close = np.abs(df['high'] - df['close'].shift())
low_close = np.abs(df['low'] - df['close'].shift())
tr = df[['high', 'low', 'close']].copy()
tr['tr'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
df['atr'] = tr['tr'].rolling(window=14).mean()

bar = df[df['time'] == target_dt]
print("ATR at 22 July 13:00 (Server time):")
print(bar[['time', 'atr']].to_string(index=False))

# What about BKK time? If the screenshot says 13:06 BKK, it means Server Time is 06:06 UTC (or 06:00 bar).
# Let's check 22 July 06:00 Server time.
target_dt2 = datetime.strptime("2026-07-22 06:00", "%Y-%m-%d %H:%M")
rates2 = mt5.copy_rates_from(sym, mt5.TIMEFRAME_H1, target_dt2, 30)
df2 = pd.DataFrame(rates2)
df2['time'] = pd.to_datetime(df2['time'], unit='s')

high_low2 = df2['high'] - df2['low']
high_close2 = np.abs(df2['high'] - df2['close'].shift())
low_close2 = np.abs(df2['low'] - df2['close'].shift())
tr2 = df2[['high', 'low', 'close']].copy()
tr2['tr'] = pd.concat([high_low2, high_close2, low_close2], axis=1).max(axis=1)
df2['atr'] = tr2['tr'].rolling(window=14).mean()

bar2 = df2[df2['time'] == target_dt2]
print("\nATR at 22 July 06:00 (Server time - translates to 13:00 BKK):")
print(bar2[['time', 'atr']].to_string(index=False))

mt5.shutdown()
