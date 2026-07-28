import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

symbols = ["XAUUSD.iux", "BTCUSD.iux", "ETHUSD.iux"]
target_dt = datetime.strptime("2026-07-18 03:00", "%Y-%m-%d %H:%M")

with open(r"d:\Project\Copter01_AI_Bot_2\scratch\bar_result.txt", "w", encoding="utf-8") as f:
    for sym in symbols:
        # fetch 200 bars before target_dt
        rates = mt5.copy_rates_from(sym, mt5.TIMEFRAME_H1, target_dt, 200)
        if rates is None or len(rates) == 0:
            f.write(f"No data for {sym}\n\n")
            continue
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # calc ATR(14)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = df[['high', 'low', 'close']].copy()
        tr['tr'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr['tr'].rolling(window=14).mean()
        df['fuel'] = df['atr'] * 3.42
        
        bar = df[df['time'] == target_dt]
        if bar.empty:
            f.write(f"--- {sym} --- NO BAR AT EXACTLY {target_dt}\n")
            f.write("Closest bars:\n")
            f.write(df.tail(3)[['time', 'open', 'high', 'low', 'close', 'atr', 'fuel']].to_string() + "\n\n")
        else:
            f.write(f"--- {sym} --- BAR FOUND AT {target_dt}\n")
            f.write(bar[['time', 'open', 'high', 'low', 'close', 'atr', 'fuel']].to_string() + "\n\n")

mt5.shutdown()
print("Done")
