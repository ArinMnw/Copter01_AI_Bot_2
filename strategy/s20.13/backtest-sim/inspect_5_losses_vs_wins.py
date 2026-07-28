import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from strategy20_13_23 import compute_indicators_df, evaluate_bar, get_fuel_multiplier
import config

def inspect_losses_vs_wins(days=700, symbol="XAUUSD.iux", compound=1.5):
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

    wins_list = []
    losses_list = []
    
    for i in range(100, len(rates) - 10):
        res = evaluate_bar(df_master, i, tf="H1")
        if res and res.get("signal") in ["BUY", "SELL"]:
            cur = df_master.iloc[i]
            signal = res["signal"]; entry = res["entry"]; sl = res["sl"]; tp = res["tp"]
            
            # check if closed as win or loss
            dt_str = datetime.fromtimestamp(rates[i]['time']).strftime('%Y-%m-%d %H:%M:%S')
            future_rates = rates[i+1:]
            be_trig = entry + ((tp - entry) * 0.4) if signal == "BUY" else entry - ((entry - tp) * 0.4)
            be_act = False; closed_type = None
            for f_bar in future_rates:
                if signal == "BUY":
                    if f_bar['low'] <= sl: closed_type = "BE" if be_act else "LOSS"; break
                    elif f_bar['high'] >= tp: closed_type = "WIN"; break
                    if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                elif signal == "SELL":
                    if f_bar['high'] >= sl: closed_type = "BE" if be_act else "LOSS"; break
                    elif f_bar['low'] <= tp: closed_type = "WIN"; break
                    if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry
            
            cur_dict = cur.to_dict()
            cur_dict['time_str'] = dt_str
            cur_dict['type'] = signal
            if closed_type == "WIN": wins_list.append(cur_dict)
            elif closed_type == "LOSS": losses_list.append(cur_dict)
            
    df_w = pd.DataFrame(wins_list)
    df_l = pd.DataFrame(losses_list)
    
    print(f"Total Wins: {len(df_w)} | Total Losses: {len(df_l)}")
    print("\n--- The 5 Losses Details ---")
    cols = ['time_str', 'type', 'rsi', 'rsi_7', 'adx', 'di_diff', 'vol_ratio', 'z_score', 'body_pct', 'atr_pct', 'dist_ema50', 'dist_ema200', 'hour', 'upper_wick_pct']
    print(df_l[cols].to_string())
    
    print("\n--- Testing Zero-Collateral Loss Block Rules ---")
    # Let's test combinations of features to see if any combination blocks ALL 5 losses while blocking ZERO wins!
    for idx_l, row_l in df_l.iterrows():
        t = row_l['time_str']
        # let's find rules that separate row_l from df_w
        print(f"\nAnalyzing Loss at {t} ({row_l['type']}):")
        # print top features where row_l is extreme compared to df_w
        for col in ['rsi', 'rsi_7', 'adx', 'di_diff', 'vol_ratio', 'z_score', 'body_pct', 'atr_pct', 'dist_ema50', 'dist_ema200', 'hour', 'upper_wick_pct']:
            val = row_l[col]
            min_w = df_w[col].min(); max_w = df_w[col].max()
            if val < min_w:
                print(f"  EXCLUSION: {col} = {val:.2f} is BELOW win minimum ({min_w:.2f})!")
            elif val > max_w:
                print(f"  EXCLUSION: {col} = {val:.2f} is ABOVE win maximum ({max_w:.2f})!")

    mt5.shutdown()

if __name__ == "__main__":
    inspect_losses_vs_wins()
