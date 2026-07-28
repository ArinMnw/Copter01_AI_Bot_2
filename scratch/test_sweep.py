import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import sys, os
sys.path.append(os.path.abspath('.'))
import config

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

sym = "XAUUSD.iux"
rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 500)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

high_low = df['high'] - df['low']
high_close = np.abs(df['high'] - df['close'].shift())
low_close = np.abs(df['low'] - df['close'].shift())
tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
df['atr'] = tr.rolling(window=14).mean()

for i in range(50, len(df)):
    current_bar = df.iloc[i]
    lookback_bars = df.iloc[i-15:i]
    
    local_low = lookback_bars['low'].min()
    local_high = lookback_bars['high'].max()
    
    if current_bar['low'] < local_low and current_bar['close'] > local_low and current_bar['close'] > current_bar['open']:
        print(f"BUY Sweep at {current_bar['time']} (Low={current_bar['low']}, LocalLow={local_low})")
        
    if current_bar['high'] > local_high and current_bar['close'] < local_high and current_bar['close'] < current_bar['open']:
        print(f"SELL Sweep at {current_bar['time']} (High={current_bar['high']}, LocalHigh={local_high})")

mt5.shutdown()
