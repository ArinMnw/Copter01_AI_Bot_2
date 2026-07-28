import MetaTrader5 as mt5
import pandas as pd
import sys

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

sym = "XAUUSD.iux"
rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 1000)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

print("=== 01-07-2026 Bars ===")
print(df[(df['time'] >= '2026-07-01 07:00') & (df['time'] <= '2026-07-01 18:00')][['time', 'open', 'high', 'low', 'close']])

print("\n=== 16-07 to 17-07 Bars ===")
print(df[(df['time'] >= '2026-07-16 20:00') & (df['time'] <= '2026-07-18 02:00')][['time', 'open', 'high', 'low', 'close']])

mt5.shutdown()
