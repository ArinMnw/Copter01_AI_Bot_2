import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import config

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

symbol = getattr(config, "SYMBOL", "XAUUSD")
print(f"Using symbol: {symbol}")

rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 500)
if rates is None or len(rates) == 0:
    print(f"No rates found for {symbol}")
else:
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    print("Last 10 bars (Server Time):")
    print(df.tail(10)[['time', 'open', 'high', 'low', 'close']])
    
    # Check if there is any bar around 18th July
    mask = df['time'].dt.day == 18
    if mask.any():
        print("\nBars on 18th July:")
        print(df[mask][['time', 'open', 'high', 'low', 'close']])
    else:
        print("\nNo bars found on 18th July.")

mt5.shutdown()
