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

filtered = df[(df['time'] >= '2026-07-09') & (df['time'] <= '2026-07-10 12:00')]
print(filtered[['time', 'open', 'high', 'low', 'close']])

mt5.shutdown()
