import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pytz

mt5.initialize()
tz = pytz.timezone("Asia/Bangkok")
start = datetime(2026, 2, 7, 0, 0, tzinfo=tz)
end = datetime(2026, 2, 12, 0, 0, tzinfo=tz)

rates = mt5.copy_rates_range("XAUUSD.iux", mt5.TIMEFRAME_H1, start, end)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df['time_dt'] = df['time'].dt.tz_localize('UTC').dt.tz_convert(tz)
df['body'] = abs(df['close'] - df['open'])
df['range'] = df['high'] - df['low']
df['is_green'] = df['close'] > df['open']
df['is_red'] = df['close'] < df['open']

# Calculate SMA for S1
df['sma50'] = df['close'].rolling(50).mean()

print("Bars around 10-02-2026 04:00:")
target_time = datetime(2026, 2, 10, 4, 0, tzinfo=tz)
mask = (df['time_dt'] >= target_time - timedelta(hours=5)) & (df['time_dt'] <= target_time + timedelta(hours=5))
print(df[mask][['time_dt', 'open', 'high', 'low', 'close', 'body', 'range']])

mt5.shutdown()
