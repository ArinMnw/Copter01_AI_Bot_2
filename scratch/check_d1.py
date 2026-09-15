import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd
import sys
import os

mt5.initialize(r'D:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101182459\mt5\terminal64.exe')
start = datetime.now() - timedelta(days=365)
rates = mt5.copy_rates_from_pos('XAUUSD.iux', mt5.TIMEFRAME_D1, 0, 365)
if rates is not None:
    df_d1 = pd.DataFrame(rates)
    df_d1['time_dt'] = pd.to_datetime(df_d1['time'], unit='s') + timedelta(hours=1)
    df_d1['bear_fvg_raw'] = df_d1['low'].shift(2) > df_d1['high']
    df_d1['bear_fvg_top'] = df_d1['low'].shift(2)
    df_d1['bear_fvg_bot'] = df_d1['high']
    
    current_time = pd.to_datetime('2026-03-10 18:00:00')
    idx_arr = df_d1.index[df_d1['time_dt'] <= current_time]
    idx = idx_arr[-1] if len(idx_arr) > 0 else -1
    print("idx:", idx)
    past_d1 = df_d1.iloc[max(0, idx-30):idx+1]
    recent_ll = past_d1['low'].min()
    print("past_d1 low min:", recent_ll)
    
    print("02-02-2026 low:", df_d1[df_d1['time_dt'] == pd.to_datetime('2026-02-02')]['low'].values)
    print("Is 02-02-2026 in past_d1?", pd.to_datetime('2026-02-02') in past_d1['time_dt'].values)
    print("past_d1 head:\n", past_d1[['time_dt', 'low']].head(5))

mt5.shutdown()
