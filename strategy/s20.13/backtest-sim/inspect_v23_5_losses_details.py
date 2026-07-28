import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from strategy20_13_23 import compute_indicators_df, evaluate_bar
import config

def inspect_details(days=700, symbol="XAUUSD.iux"):
    path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
    if not mt5.initialize(path=path): return
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start_time, end_time)
    
    df_master = compute_indicators_df(rates)
    df_master['upper_wick'] = df_master['high'] - np.maximum(df_master['open'], df_master['close'])
    df_master['lower_wick'] = np.minimum(df_master['open'], df_master['close']) - df_master['low']
    df_master['upper_wick_pct'] = df_master['upper_wick'] / (df_master['range'] + 0.0001)
    df_master['lower_wick_pct'] = df_master['lower_wick'] / (df_master['range'] + 0.0001)
    df_master['dist_ema50'] = df_master['close'] - df_master['ema_50']
    df_master['dist_ema200'] = df_master['close'] - df_master['ema_200']
    df_master['hour'] = df_master['time_dt'].dt.hour

    loss_times = [
        "2024-10-21 23:00:00",
        "2024-11-15 23:00:00",
        "2025-04-09 00:00:00",
        "2025-05-19 08:00:00",
        "2025-06-04 12:00:00"
    ]
    
    print("================== DETAILS OF THE 5 REMAINING LOSSES IN V23 ==================")
    for i in range(100, len(rates) - 10):
        dt_str = datetime.fromtimestamp(rates[i]['time']).strftime('%Y-%m-%d %H:%M:%S')
        if dt_str in loss_times:
            cur = df_master.iloc[i]
            print(f"\nLoss Time: {dt_str} | Close: {cur['close']:.2f}")
            print(f"  RSI: {cur['rsi']:.1f} | RSI7: {cur['rsi_7']:.1f} | ADX: {cur['adx']:.1f} | DI_Diff: {cur['di_diff']:.1f}")
            print(f"  VolRatio: {cur['vol_ratio']:.2f} | Z_Score: {cur['z_score']:.2f} | Body%: {cur['body_pct']:.2f} | ATR%: {cur['atr_pct']:.2f}%")
            print(f"  DistEMA50: {cur['dist_ema50']:.1f} | DistEMA200: {cur['dist_ema200']:.1f} | uWick%: {cur['upper_wick_pct']:.2f} | lWick%: {cur['lower_wick_pct']:.2f} | Hour: {cur['hour']}")

    mt5.shutdown()

if __name__ == "__main__":
    inspect_details()
