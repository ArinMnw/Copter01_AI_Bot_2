import MetaTrader5 as mt5
import pandas as pd
import sys
from datetime import datetime, timedelta
sys.path.append('d:\\Project\\Copter01_AI_Bot_2')
sys.path.append('d:\\Project\\Copter01_AI_Bot_2\\strategy\\s20.13')
from strategy20_13_17 import strategy_20_13_17
from strategy20_13_15 import strategy_20_13_15

mt5.initialize()
symbol = "XAUUSD.iux"
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 1000)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
print('Fetched bars:', len(df))

signals_15 = 0
signals_17 = 0
for i in range(50, len(df)):
    res15 = strategy_20_13_15(rates[i-50:i+1], tf='H1')
    res17 = strategy_20_13_17(rates[i-50:i+1], tf='H1')
    if res15['signal'] != 'WAIT':
        signals_15 += 1
        print(f"15 Signal at {df.iloc[i]['time']}: {res15['signal']}")
    if res17['signal'] != 'WAIT':
        signals_17 += 1
        print(f"17 Signal at {df.iloc[i]['time']}: {res17['signal']}")

print(f"Total 15 signals: {signals_15}, Total 17 signals: {signals_17}")
mt5.shutdown()
