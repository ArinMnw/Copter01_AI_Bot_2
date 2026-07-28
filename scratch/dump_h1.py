import MetaTrader5 as mt5
import pandas as pd
import sys

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

sym = "XAUUSD.iux"
rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 100)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
print("Last 20 bars in MT5 (H1):")
print(df.tail(20)[['time', 'open', 'high', 'low', 'close']].to_string(index=False))

mt5.shutdown()
