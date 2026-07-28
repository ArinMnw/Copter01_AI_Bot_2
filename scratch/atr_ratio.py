import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
import sys

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

sym = "XAUUSD.iux"

def get_atr(tf_code, n=5000):
    rates = mt5.copy_rates_from_pos(sym, tf_code, 0, n)
    df = pd.DataFrame(rates)
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.mean() # Average True Range over a long period

atr_h1 = get_atr(mt5.TIMEFRAME_H1, 10000)
atr_h4 = get_atr(mt5.TIMEFRAME_H4, 2500)
atr_h12 = get_atr(mt5.TIMEFRAME_H12, 1000)
atr_d1 = get_atr(mt5.TIMEFRAME_D1, 500)

print(f"Historical Average ATR H1: {atr_h1:.3f}")
print(f"Historical Average ATR H4: {atr_h4:.3f} (Ratio H4/H1: {atr_h4/atr_h1:.3f})")
print(f"Historical Average ATR H12: {atr_h12:.3f} (Ratio H12/H1: {atr_h12/atr_h1:.3f})")
print(f"Historical Average ATR D1: {atr_d1:.3f} (Ratio D1/H1: {atr_d1/atr_h1:.3f})")

mt5.shutdown()
