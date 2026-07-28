import MetaTrader5 as mt5
import pandas as pd
import sys

if not mt5.initialize():
    sys.exit()

rates = mt5.copy_rates_from_pos("XAUUSD.iux", mt5.TIMEFRAME_H1, 0, 1000)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
df['rsi'] = 100 - (100 / (1 + rs))

# Check Clip 2 trade properly: 2026-07-09 19:00 (Server Time)
row = df[df['time'] == '2026-07-09 19:00:00']
if not row.empty:
    bar = row.iloc[0]
    print(f"Time: {bar['time']}")
    print(f"Close: {bar['close']}")
    print(f"EMA 50: {bar['ema_50']}")
    print(f"EMA 200: {bar['ema_200']}")
    print(f"RSI: {bar['rsi']}")

mt5.shutdown()
