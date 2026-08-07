import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
import pytz
import sys

sys.path.append('d:/Project/Copter01_AI_Bot_2')
import strategy1, strategy11

mt5.initialize()
tz = pytz.timezone('Asia/Bangkok')
start = datetime(2026, 2, 16, 0, 0, tzinfo=tz)
end = datetime(2026, 2, 19, 0, 0, tzinfo=tz)

rates = mt5.copy_rates_range('XAUUSD.iux', mt5.TIMEFRAME_H1, start, end)
rates_dict = [
    {
        'time': r['time'],
        'open': r['open'],
        'high': r['high'],
        'low': r['low'],
        'close': r['close'],
        'tick_volume': r['tick_volume'],
        'spread': r['spread'],
        'real_volume': r['real_volume']
    }
    for r in rates
]
strategy11.reset_state('H1')

for i in range(10, len(rates_dict)):
    current = rates_dict[:i]
    last_bar = current[-1]
    last_time = pd.to_datetime(last_bar['time'], unit='s').tz_localize('UTC').tz_convert(tz)
    
    s1_res = strategy1.strategy_1(current, 'H1')
    if s1_res and s1_res.get('signal') == 'BUY':
        print(f"[{last_time}] S1 BUY: {s1_res['pattern']}")
        strategy11.record_s1_pattern('H1', 'BUY', s1_res['candles'], last_bar['time'])
        
    s11_res = strategy11.strategy_11(current, 'H1')
    if s11_res and s11_res.get('signal') == 'BUY':
        print(f"[{last_time}] S11 Triggered! Entry: {s11_res['entry']}, SL: {s11_res['sl']}, TP: {s11_res['tp']} {s11_res['pattern']}")

mt5.shutdown()
