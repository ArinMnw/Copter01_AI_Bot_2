import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import sys

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

sym = "XAUUSD.iux"
rates = mt5.copy_rates_from(sym, mt5.TIMEFRAME_D1, datetime(2026, 7, 24), 10)
if rates is not None and len(rates) > 0:
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['range'] = df['high'] - df['low']
    df['range_pct_open'] = (df['range'] / df['open']) * 100
    df['range_pct_low'] = (df['range'] / df['low']) * 100
    print("Daily Bars for XAUUSD:")
    print(df[['time', 'open', 'high', 'low', 'close', 'range', 'range_pct_open', 'range_pct_low']].to_string())

mt5.shutdown()
