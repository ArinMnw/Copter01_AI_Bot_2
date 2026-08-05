import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import timedelta
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 's20.13')))
import strategy20_13_24

mt5.initialize()
symbol = "XAUUSD.iux"
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H12, 0, 120)
df = strategy20_13_24.compute_indicators_df(rates)
df['time_dt'] = pd.to_datetime(df['time'], unit='s') + timedelta(hours=1)

df['sma50'] = df['close'].rolling(window=50).mean()
df['sma200'] = df['close'].rolling(window=200).mean()

df['body'] = np.abs(df['close'] - df['open'])
df['range'] = df['high'] - df['low']

df['is_green'] = df['close'] > df['open']
df['is_red'] = df['close'] < df['open']
df['is_green_doji'] = df['is_green'] & (df['body'] <= df['range'] * 0.35)
df['is_red_doji'] = df['is_red'] & (df['body'] <= df['range'] * 0.35)

df['naiya_buy_base'] = df['is_green'] & df['is_green_doji'].shift(1) & df['is_red'].shift(2) & \
                       (df['low'].shift(1) < df['low']) & (df['low'].shift(1) < df['low'].shift(2)) & \
                       (df['close'] > df['high'].shift(1))

list_of_dicts = df.to_dict('records')
for i in range(1, len(list_of_dicts)):
    row_dict = list_of_dicts[i]
    row = type('obj', (object,), row_dict)()
    
    if row.naiya_buy_base:
        print(f"Naiya BUY base found on H12 at {row.time_dt}")

mt5.shutdown()
