import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pytz

mt5.initialize()
tz = pytz.timezone("Asia/Bangkok")
end = datetime(2026, 2, 7, 0, 0, tzinfo=tz)
start = end - timedelta(days=10)

rates = mt5.copy_rates_range("XAUUSD.iux", mt5.TIMEFRAME_H1, start, end)
df = pd.DataFrame(rates)
df['time_dt'] = pd.to_datetime(df['time'], unit='s')
df['time_dt'] = df['time_dt'].dt.tz_localize('UTC').dt.tz_convert(tz)
df['time_diff'] = df['time_dt'].diff()
df['prev_close'] = df['close'].shift(1)
df['prev_open_2'] = df['open'].shift(2)
df['prev_low_2'] = df['low'].shift(2)
df['prev_high_2'] = df['high'].shift(2)

df['inst_gap_buy'] = (df['time_diff'].dt.total_seconds() > 3600) & (df['open'] > df['prev_close'])
df['inst_gap_sell'] = (df['time_diff'].dt.total_seconds() > 3600) & (df['open'] < df['prev_close'])

for idx, row in df.iterrows():
    if row.inst_gap_buy == True:
        limit_p = row.prev_open_2 if not pd.isna(row.prev_open_2) else row.prev_close
        sl = row.prev_low_2 if not pd.isna(row.prev_low_2) else row.low
        print(f"Gap UP at {row.time_dt} - Buy Limit: {limit_p}, SL: {sl}")
    if row.inst_gap_sell == True:
        limit_p = row.prev_open_2 if not pd.isna(row.prev_open_2) else row.prev_close
        sl = row.prev_high_2 if not pd.isna(row.prev_high_2) else row.high
        print(f"Gap DOWN at {row.time_dt} - Sell Limit: {limit_p}, SL: {sl}")

mt5.shutdown()
