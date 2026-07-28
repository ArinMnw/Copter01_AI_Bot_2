import MetaTrader5 as mt5
import pandas as pd
import sys

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

sym = "XAUUSD.iux"
rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 500)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

# Find all bars with High between 4135 and 4140 before July 17
filtered = df[(df['time'] < '2026-07-17') & (df['high'] >= 4135) & (df['high'] <= 4145)]
print(filtered[['time', 'open', 'high', 'low', 'close']])

mt5.shutdown()
