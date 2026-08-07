import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pytz
import sys
sys.path.append('d:/Project/Copter01_AI_Bot_2')
import strategy11
import strategy1

mt5.initialize()
tz = pytz.timezone("Asia/Bangkok")
start = datetime(2026, 2, 7, 0, 0, tzinfo=tz)
end = datetime(2026, 2, 11, 20, 0, tzinfo=tz)

rates = mt5.copy_rates_range("XAUUSD.iux", mt5.TIMEFRAME_H1, start, end)
rates_list = list(rates)
rates_dict = [dict(zip(rates.dtype.names, r)) for r in rates_list]

tf_str = "H1"
strategy11.reset_state(tf_str)

for i in range(10, len(rates_dict)):
    current_rates = rates_dict[:i]
    last_bar = current_rates[-1]
    last_time = pd.to_datetime(last_bar['time'], unit='s').tz_localize('UTC').tz_convert(tz)
    
    s1_res = strategy1.strategy_1(current_rates, tf_str)
    if last_time.day == 10 and last_time.hour == 4:
        print(f"[{last_time}] RAW S1 RES: {s1_res}")
        
    if s1_res and s1_res.get('signal') == 'SELL':
        print(f"[{last_time}] S1 Triggered: {s1_res['pattern']}")
        strategy11.record_s1_pattern(tf_str, s1_res['signal'], s1_res['candles'], last_bar['time'])
    elif s1_res and s1_res.get('signal') == 'WAIT':
        reason = s1_res.get('reason', '')
        if "SELL" in reason and last_time.hour == 4:
            print(f"[{last_time}] WAIT: {reason}")
        
    s11_res = strategy11.strategy_11(current_rates, tf_str)
    if s11_res:
        if s11_res.get('signal') == 'SELL':
            print(f"[{last_time}] S11 Triggered! {s11_res['signal']} Entry: {s11_res['entry']}, SL: {s11_res['sl']}, TP: {s11_res['tp']}")
            print(s11_res['pattern'])
        elif s11_res.get('signal') == 'WAIT' and last_time.day == 10 and last_time.hour == 6:
            print(f"[{last_time}] S11 WAIT: {s11_res.get('reason')}")

mt5.shutdown()
