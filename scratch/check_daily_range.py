import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import sys

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

sym = "XAUUSD.iux"
# The current bar is 2026-07-17 20:00, so let's get D1 bars for the last few days
rates = mt5.copy_rates_from(sym, mt5.TIMEFRAME_D1, datetime(2026, 7, 18), 10)
if rates is not None and len(rates) > 0:
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['range'] = df['high'] - df['low']
    df['range_pct_open'] = (df['range'] / df['open']) * 100
    df['range_pct_close'] = (df['range'] / df['close']) * 100
    df['range_pct_low'] = (df['range'] / df['low']) * 100
    print("Daily Bars for XAUUSD:")
    print(df[['time', 'open', 'high', 'low', 'close', 'range', 'range_pct_open']].to_string())
    
    # Try ATR(14) of D1
    rates_100 = mt5.copy_rates_from(sym, mt5.TIMEFRAME_D1, datetime(2026, 7, 18), 100)
    df2 = pd.DataFrame(rates_100)
    df2['range'] = df2['high'] - df2['low']
    df2['atr'] = df2['range'].rolling(14).mean()
    df2['atr_pct'] = (df2['atr'] / df2['open']) * 100
    print("\nRecent D1 ATR(14):")
    print(df2.tail(5)[['time', 'atr', 'atr_pct']])

mt5.shutdown()
