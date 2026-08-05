import pandas as pd
import numpy as np

# Load target orders
orders = [
    {"num": 1, "type": "SELL", "time_bkk": "2026-05-12 01:00", "entry": 4769.61},
    {"num": 2, "type": "SELL", "time_bkk": "2026-05-12 02:00", "entry": 4773.49},
    {"num": 3, "type": "SELL", "time_bkk": "2026-05-19 02:00", "entry": 4589.28},
    {"num": 4, "type": "SELL", "time_bkk": "2026-05-19 02:00", "entry": 4589.28},
    {"num": 5, "type": "SELL", "time_bkk": "2026-05-29 17:00", "entry": 4595.29},
    {"num": 6, "type": "SELL", "time_bkk": "2026-06-02 09:00", "entry": 4541.48},
    {"num": 7, "type": "BUY", "time_bkk": "2026-06-08 02:00", "entry": 4339.72},
    {"num": 8, "type": "SELL", "time_bkk": "2026-06-15 16:00", "entry": 4369.3},
    {"num": 9, "type": "SELL", "time_bkk": "2026-06-18 09:00", "entry": 4309.44},
    {"num": 10, "type": "BUY", "time_bkk": "2026-06-30 03:00", "entry": 3942.68},
    {"num": 11, "type": "SELL", "time_bkk": "2026-07-01 03:00", "entry": 3999.81},
    {"num": 12, "type": "SELL", "time_bkk": "2026-07-01 17:00", "entry": 4094.59},
    {"num": 13, "type": "BUY", "time_bkk": "2026-07-01 09:00", "entry": 3960.16},
    {"num": 14, "type": "BUY", "time_bkk": "2026-07-01 09:00", "entry": 3960.16},
    {"num": 15, "type": "SELL", "time_bkk": "2026-07-07 20:00", "entry": 4145.2},
    {"num": 16, "type": "SELL", "time_bkk": "2026-07-08 00:00", "entry": 4106.04},
    {"num": 17, "type": "BUY", "time_bkk": "2026-07-08 17:00", "entry": 4021.78},
    {"num": 18, "type": "SELL", "time_bkk": "2026-07-06 01:00", "entry": 4201.83},
    {"num": 19, "type": "BUY", "time_bkk": "2026-07-08 17:00", "entry": 4021.78},
    {"num": 20, "type": "SELL", "time_bkk": "2026-07-09 18:00", "entry": 4138.08},
    {"num": 21, "type": "SELL", "time_bkk": "2026-07-14 14:00", "entry": 4102.97},
    {"num": 22, "type": "SELL", "time_bkk": "2026-07-14 14:00", "entry": 4102.97},
    {"num": 23, "type": "BUY", "time_bkk": "2026-07-17 15:00", "entry": 3959.72},
    {"num": 24, "type": "BUY", "time_bkk": "2026-07-17 15:00", "entry": 3959.72},
    {"num": 25, "type": "BUY", "time_bkk": "2026-07-17 13:00", "entry": 3990.0},
    {"num": 26, "type": "SELL", "time_bkk": "2026-07-14 14:00", "entry": 4102.97},
    {"num": 27, "type": "SELL", "time_bkk": "2026-07-15 20:00", "entry": 4081.19},
    {"num": 28, "type": "BUY", "time_bkk": "2026-07-17 15:00", "entry": 3959.72},
    {"num": 29, "type": "SELL", "time_bkk": "2026-07-22 05:00", "entry": 4141.71},
    {"num": 30, "type": "SELL", "time_bkk": "2026-07-22 17:00", "entry": 4165.99},
    {"num": 31, "type": "SELL", "time_bkk": "2026-07-23 03:00", "entry": 4141.06},
    {"num": 32, "type": "SELL", "time_bkk": "2026-07-23 03:00", "entry": 4141.06},
    {"num": 33, "type": "BUY", "time_bkk": "2026-07-24 05:00", "entry": 4023.2},
    {"num": 34, "type": "BUY", "time_bkk": "2026-07-24 05:00", "entry": 4023.2},
    {"num": 35, "type": "BUY", "time_bkk": "2026-07-24 14:00", "entry": 4051.71},
]

import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone

BKK = timezone(timedelta(hours=7))
mt5.initialize()
rates = mt5.copy_rates_from_pos("XAUUSD.iux", mt5.TIMEFRAME_H1, 0, 8000)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df['time_bkk'] = df['time'].dt.tz_localize('UTC').dt.tz_convert(BKK).dt.strftime('%Y-%m-%d %H:%M')

df['sma12'] = df['close'].rolling(12).mean()
df['sma20'] = df['close'].rolling(20).mean()
df['sma50'] = df['close'].rolling(50).mean()
df['sma200'] = df['close'].rolling(200).mean()
delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
df['rsi'] = 100 - (100 / (1 + rs))

for o in orders:
    t_bkk = o['time_bkk']
    row = df[df['time_bkk'] == t_bkk]
    if len(row) > 0:
        r = row.iloc[0]
        sma50 = r['sma50']
        sma200 = r['sma200']
        rsi = r['rsi']
        trend = "UP" if sma50 > sma200 else "DOWN"
        print(f"Order {o['num']:02d} [{o['type']}] {t_bkk} | Trend: {trend} (SMA50:{sma50:.1f}, SMA200:{sma200:.1f}) | RSI: {rsi:.1f}")
    else:
        print(f"Order {o['num']:02d} [{o['type']}] {t_bkk} | NOT FOUND IN H1 DATA")
mt5.shutdown()
