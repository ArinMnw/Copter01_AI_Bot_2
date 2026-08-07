import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pytz

mt5.initialize()
tz = pytz.timezone("Asia/Bangkok")
start = datetime(2026, 2, 7, 0, 0, tzinfo=tz)
end = datetime(2026, 2, 11, 0, 0, tzinfo=tz)

rates = mt5.copy_rates_range("XAUUSD.iux", mt5.TIMEFRAME_H1, start, end)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df['time_dt'] = df['time'].dt.tz_localize('UTC').dt.tz_convert(tz)
df['body'] = abs(df['close'] - df['open'])
df['range'] = df['high'] - df['low']

df['is_green'] = df['close'] > df['open']
df['is_red'] = df['close'] < df['open']
df['is_green_doji'] = df['is_green'] & (df['body'] <= df['range'] * 0.35)
df['is_red_doji'] = df['is_red'] & (df['body'] <= df['range'] * 0.35)

df['naiya_doji_sell_base'] = df['is_red'] & df['is_red_doji'].shift(1) & df['is_green'].shift(2) & \
                        (df['high'].shift(1) > df['high']) & (df['high'].shift(1) > df['high'].shift(2)) & \
                        (df['close'] < df['low'].shift(1))

# Pinbar
df['is_red_pinbar'] = df['is_red'] & (df['open'] - df['low'] <= df['range'] * 0.25) & (df['high'] - df['open'] >= df['range'] * 0.5)

df['naiya_pinbar_sell_base'] = df['is_red'] & df['is_red_pinbar'].shift(1) & df['is_green'].shift(2) & \
                        (df['high'].shift(1) > df['high']) & (df['high'].shift(1) > df['high'].shift(2)) & \
                        (df['close'] < df['low'].shift(1))

df['prev_low'] = df['low'].shift(1)
df['prev_high'] = df['high'].shift(1)
df['prev_low_2'] = df['low'].shift(2)
df['prev_high_2'] = df['high'].shift(2)

df['naiya_fvg_sell'] = df['is_red'] & df['is_red'].shift(1) & df['is_green'].shift(2) & \
                        (df['high'].shift(1) > df['high'].shift(2)) & \
                        (df['close'] < df['low'].shift(2)) & \
                        (df['high'] < df['low'].shift(2)) # FVG gap

df['s1_sell'] = df['naiya_doji_sell_base'] | df['naiya_pinbar_sell_base'] | df['naiya_fvg_sell']

print("S1 Sell triggers:")
res = df[df['s1_sell'] == True]
print(res[['time_dt', 'open', 'high', 'low', 'close', 'naiya_doji_sell_base', 'naiya_pinbar_sell_base', 'naiya_fvg_sell']])

if len(res) > 0:
    idx = res.index[0]
    print("\nBars around the trigger:")
    print(df.iloc[idx-3:idx+2][['time_dt', 'open', 'high', 'low', 'close', 'is_green', 'is_red', 'is_red_doji', 'is_red_pinbar']])

mt5.shutdown()
