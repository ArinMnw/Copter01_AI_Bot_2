import pandas as pd
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5
import sys
sys.path.append('d:/Project/Copter01_AI_Bot_2')
import strategy1
import strategy11

BKK = timezone(timedelta(hours=7))
mt5.initialize()
symbol = 'XAUUSD.iux'

start = datetime(2026, 6, 1, 0, 0, tzinfo=BKK)
end = datetime(2026, 6, 2, 14, 0, tzinfo=BKK)
rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M30, start, end)

df = pd.DataFrame(rates)
df['time_dt'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert(BKK)

for i in range(50, len(rates)):
    current_rates = rates[:i+1]
    
    s1_res = strategy1.strategy_1(current_rates.tolist(), 'M30')
    if s1_res and s1_res.get('signal') in ['BUY', 'SELL']:
        strategy11.record_s1_pattern('M30', s1_res['signal'], current_rates.tolist(), current_rates[-1]['time'])
        print(f"S1 Signal: {s1_res.get('signal')} at {df.iloc[i].time_dt}")
        
    s11_res = strategy11.strategy_11(current_rates.tolist(), 'M30')
    if s11_res and s11_res.get('signal'):
        print(f"S11 Fibo: {s11_res.get('signal')} at {df.iloc[i].time_dt}")

mt5.shutdown()
