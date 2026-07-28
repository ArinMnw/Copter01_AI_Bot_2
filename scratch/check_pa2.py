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

print("\n=== 17-07 late bars ===")
print(df[(df['time'] >= '2026-07-17 19:00') & (df['time'] <= '2026-07-18 05:00')][['time', 'open', 'high', 'low', 'close']])

print("\n=== Highs to check ===")
print("16-07-2026 22:00 (Wait, 16-07 20:00? Let's check 22:00)")
print(df[(df['time'] == '2026-07-16 22:00')][['time', 'high']])
print("17-07-2026 10:00")
print(df[(df['time'] == '2026-07-17 10:00')][['time', 'high']])

mt5.shutdown()
