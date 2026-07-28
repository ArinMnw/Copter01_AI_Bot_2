import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

sym = "XAUUSD.iux"
target_dt = datetime.strptime("2026-07-17 20:00", "%Y-%m-%d %H:%M")

rates = mt5.copy_rates_from(sym, mt5.TIMEFRAME_H1, target_dt, 30)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
print(df[['time', 'open', 'high', 'low', 'close']].to_string())

mt5.shutdown()
