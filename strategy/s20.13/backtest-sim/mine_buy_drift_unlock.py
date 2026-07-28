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

def mine_buy_drift(days=700, symbol="XAUUSD.iux", compound=1.5):
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

    wins_data = []
    losses_data = []
    
    for i in range(100, len(rates) - 10):
        res = evaluate_bar(df_master, i, tf="H1")
        if res and res.get("signal") == "WAIT" and "BUY Low Volatility Drift Block" in res.get("reason", ""):
            # Let's see what would have happened if we entered BUY here!
            cur = df_master.iloc[i]
            recent_3 = df_master.iloc[i-2:i+1]
            active_mode = getattr(config, "S20_13_ACTIVE_MODE", 2.6)
            target_tf_buy = getattr(config, "S20_13_TARGET_TF_BUY", "H12")
            
            entry = cur['close']
            sweep_bottom = min(recent_3['low'].min(), cur['low'])
            sl = sweep_bottom - config.SL_BUFFER(cur['atr'])
            fuel_multiplier = get_fuel_multiplier("H1", target_tf_buy)
            fuel = cur['atr'] * active_mode * fuel_multiplier
            tp = sweep_bottom + fuel
            
            dt_str = datetime.fromtimestamp(rates[i]['time']).strftime('%Y-%m-%d %H:%M:%S')
            future_rates = rates[i+1:]
            be_trig = entry + ((tp - entry) * 0.4)
            be_act = False
            closed_type = None
            
            for f_bar in future_rates:
                if f_bar['low'] <= sl: closed_type = "BE" if be_act else "LOSS"; break
                elif f_bar['high'] >= tp: closed_type = "WIN"; break
                if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                
            cur_dict = cur.to_dict()
            cur_dict['time_str'] = dt_str
            if closed_type == "WIN": wins_data.append(cur_dict)
            elif closed_type == "LOSS": losses_data.append(cur_dict)
            
    df_w = pd.DataFrame(wins_data)
    df_l = pd.DataFrame(losses_data)
    print(f"Inside BUY Low Volatility Drift Block -> Wins: {len(df_w)} | Losses: {len(df_l)}")
    
    # Let's compare feature means and quantiles!
    features = ['rsi', 'rsi_7', 'adx', 'di_diff', 'vol_ratio', 'z_score', 'body_pct', 'atr_pct', 'dist_ema50', 'dist_ema200', 'hour', 'upper_wick_pct', 'lower_wick_pct']
    print("\n--- Feature Comparison (Wins vs Losses in Blocked BUYs) ---")
    for f in features:
        w_mean = df_w[f].mean() if len(df_w) > 0 else 0
        l_mean = df_l[f].mean() if len(df_l) > 0 else 0
        w_med = df_w[f].median() if len(df_w) > 0 else 0
        l_med = df_l[f].median() if len(df_l) > 0 else 0
        print(f"{f:<15} | Win Mean: {w_mean:8.2f} (Med: {w_med:8.2f}) | Loss Mean: {l_mean:8.2f} (Med: {l_med:8.2f})")
        
    # Let's test some rule combinations that unlock Wins while keeping Losses blocked!
    print("\n--- Testing Partial Unlock Rules ---")
    test_conds = [
        ("Unlock when dist_ema50 > 10.0 and rsi > 52", lambda r: r['dist_ema50'] > 10.0 and r['rsi'] > 52),
        ("Unlock when z_score > -0.5 and adx > 18 and di_diff > 5", lambda r: r['z_score'] > -0.5 and r['adx'] > 18 and r['di_diff'] > 5),
        ("Unlock when rsi > 50 and dist_ema200 > 20 and vol_ratio > 0.7", lambda r: r['rsi'] > 50 and r['dist_ema200'] > 20 and r['vol_ratio'] > 0.7),
        ("Unlock when rsi_7 > 55 and di_diff > 0", lambda r: r['rsi_7'] > 55 and r['di_diff'] > 0),
        ("Unlock when dist_ema50 > 0 and body_pct > 0.5", lambda r: r['dist_ema50'] > 0 and r['body_pct'] > 0.5),
        ("Unlock when z_score > 0.0 and rsi > 55", lambda r: r['z_score'] > 0.0 and r['rsi'] > 55),
    ]
    
    for name, cond in test_conds:
        w_unlocked = sum(1 for idx, r in df_w.iterrows() if cond(r))
        l_unlocked = sum(1 for idx, r in df_l.iterrows() if cond(r))
        print(f"{name:<55} | Unlocked Wins: {w_unlocked:2d}/32 | Unlocked Losses: {l_unlocked:2d}/33")

    mt5.shutdown()

if __name__ == "__main__":
    mine_buy_drift()
