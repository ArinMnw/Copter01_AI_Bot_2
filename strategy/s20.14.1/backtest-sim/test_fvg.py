import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

mt5.initialize(r'D:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101182459\mt5\terminal64.exe')
rates = mt5.copy_rates_range('XAUUSD.iux', mt5.TIMEFRAME_H1, datetime(2026, 6, 20), datetime(2026, 7, 7))
df = pd.DataFrame(rates)
df['time_dt'] = pd.to_datetime(df['time'], unit='s') + timedelta(hours=1)

ll_idx = df['low'].idxmin()
ll_val = df['low'].min()
print(f"LL: {ll_val} at {df.loc[ll_idx, 'time_dt']}")

after_ll = df.loc[ll_idx:].copy()
after_ll['low_roll'] = after_ll['low'].rolling(3, center=True).min()
swings = after_ll[after_ll['low'] == after_ll['low_roll']]
hl_idx = swings['low'].idxmin()
hl_val = swings.loc[hl_idx, 'low']
hl_time = swings.loc[hl_idx, 'time_dt']
print(f"HL: {hl_val} at {hl_time}")

print("--- Surrounding Candles ---")
surround = df.loc[max(0, hl_idx-5):min(len(df)-1, hl_idx+5)]
print(surround[['time_dt', 'open', 'high', 'low', 'close']])

print("--- Looking for Bullish FVG (c1.high < c3.low) ---")
for i in range(max(2, hl_idx-10), min(len(df), hl_idx+10)):
    c1 = df.iloc[i-2]
    c3 = df.iloc[i]
    if c1['high'] < c3['low']:
        print(f"FVG Found ending at {c3['time_dt']} Gap: {c1['high']} - {c3['low']}")
