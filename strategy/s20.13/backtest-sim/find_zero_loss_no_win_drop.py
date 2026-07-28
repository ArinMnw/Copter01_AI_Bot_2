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

def find_precision_rules(days=700, symbol="XAUUSD.iux"):
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
    
    wins_data = []
    losses_data = []
    
    for i in range(100, len(rates) - 10):
        res = evaluate_bar(df_master, i, tf="H1")
        if res and res.get("signal") in ["BUY", "SELL"]:
            signal = res["signal"]; entry = res["entry"]; sl = res["sl"]; tp = res["tp"]
            dt_str = datetime.fromtimestamp(rates[i]['time']).strftime('%Y-%m-%d %H:%M:%S')
            cur = df_master.iloc[i].to_dict()
            cur['Time'] = dt_str
            cur['Type'] = signal
            
            # check if win or loss in baseline v23
            future_rates = rates[i+1:]
            be_trig = entry + ((tp - entry) * 0.4) if signal == "BUY" else entry - ((entry - tp) * 0.4)
            be_act = False
            closed_type = None
            for f_bar in future_rates:
                if signal == "BUY":
                    if f_bar['low'] <= sl: closed_type = "BE" if be_act else "LOSS"; break
                    elif f_bar['high'] >= tp: closed_type = "WIN"; break
                    if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                elif signal == "SELL":
                    if f_bar['high'] >= sl: closed_type = "BE" if be_act else "LOSS"; break
                    elif f_bar['low'] <= tp: closed_type = "WIN"; break
                    if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry
            
            if closed_type == "WIN":
                wins_data.append(cur)
            elif closed_type == "LOSS":
                losses_data.append(cur)
                
    df_wins = pd.DataFrame(wins_data)
    df_losses = pd.DataFrame(losses_data)
    
    print(f"Total Wins: {len(df_wins)} | Total Losses: {len(df_losses)}")
    
    # Let's test combinations of multi-variable rules for SELL (since all 5 losses are SELL)
    # Loss 1: 2024-10-21 23:00:00 -> rsi=43.5, rsi7=30.7, dist_ema50=6.0, dist_ema200=42.9, body_pct=0.48
    # Loss 2: 2024-11-15 23:00:00 -> rsi=42.0, rsi7=47.0, dist_ema50=-11.7, dist_ema200=-69.1, body_pct=0.77
    # Loss 3: 2025-04-09 00:00:00 -> rsi=42.2, rsi7=31.6, dist_ema50=-34.7, dist_ema200=-70.2, body_pct=0.90
    # Loss 4: 2025-05-19 08:00:00 -> rsi=52.6, rsi7=66.3, dist_ema50=13.6, dist_ema200=-30.2, z_score=0.86
    # Loss 5: 2025-06-04 12:00:00 -> rsi=53.9, rsi7=48.0, dist_ema50=1.6, dist_ema200=30.8, hour=5, vol_ratio=1.01

    # Let's see if we can find conditions that are TRUE for these losses but FALSE for ALL 55 wins!
    print("\nChecking rule candidates against 55 wins...")
    
    candidates = [
        ("SELL & dist_ema200 < -65.0", lambda r: r['Type'] == 'SELL' and r['dist_ema200'] < -65.0),
        ("SELL & rsi_7 < 32.0 and dist_ema50 > -40.0", lambda r: r['Type'] == 'SELL' and r['rsi_7'] < 32.0 and r['dist_ema50'] > -40.0),
        ("SELL & rsi_7 > 65.0 and z_score > 0.80", lambda r: r['Type'] == 'SELL' and r['rsi_7'] > 65.0 and r['z_score'] > 0.80),
        ("SELL & hour == 5 and vol_ratio < 1.10", lambda r: r['Type'] == 'SELL' and r['hour'] == 5 and r['vol_ratio'] < 1.10),
    ]
    
    for name, cond in candidates:
        losses_blocked = sum(1 for idx, r in df_losses.iterrows() if cond(r))
        wins_blocked = sum(1 for idx, r in df_wins.iterrows() if cond(r))
        print(f"Rule: {name:<50} | Blocks Losses: {losses_blocked}/5 | Blocks Wins: {wins_blocked}/55")
        if wins_blocked > 0:
            blocked_win_times = [r['Time'] for idx, r in df_wins.iterrows() if cond(r)]
            print(f"   Blocked Wins times: {blocked_win_times}")

    mt5.shutdown()

if __name__ == "__main__":
    find_precision_rules()
