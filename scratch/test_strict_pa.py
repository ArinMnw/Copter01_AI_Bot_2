import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import sys
from datetime import datetime, timedelta

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

sym = "XAUUSD.iux"
now = datetime.now()
start = now - timedelta(days=30)
rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 500)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

high_low = df['high'] - df['low']
high_close = np.abs(df['high'] - df['close'].shift())
low_close = np.abs(df['low'] - df['close'].shift())
tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
df['atr'] = tr.rolling(window=14).mean()

trades = []
for i in range(50, len(df)):
    current_bar = df.iloc[i]
    prev_bar = df.iloc[i-1]
    
    # 1. Sweep local extreme (e.g. 5 to 15 bars back)
    lookback_bars = df.iloc[i-15:i]
    local_low = lookback_bars['low'].min()
    local_high = lookback_bars['high'].max()
    
    # Check if a sweep happened in the last 2 bars (i or i-1)
    sweep_bar = None
    if current_bar['low'] < local_low:
        sweep_bar = current_bar
    elif prev_bar['low'] < local_low:
        sweep_bar = prev_bar
        
    # BUY setup
    if sweep_bar is not None:
        # Engulfs a recent structural high (e.g. previous bar's high or the sweep bar's high)
        if current_bar['close'] > prev_bar['high']:
            trades.append({"time": current_bar['time'], "signal": "BUY", "price": current_bar['close']})
            
    # SELL setup
    sweep_bar_sell = None
    if current_bar['high'] > local_high:
        sweep_bar_sell = current_bar
    elif prev_bar['high'] > local_high:
        sweep_bar_sell = prev_bar
        
    if sweep_bar_sell is not None:
        if current_bar['close'] < prev_bar['low']:
            trades.append({"time": current_bar['time'], "signal": "SELL", "price": current_bar['close']})

for t in trades:
    print(f"{t['time']} | {t['signal']} at {t['price']}")

mt5.shutdown()
