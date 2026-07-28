import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from strategy20_13_23 import compute_indicators_df, evaluate_bar, get_fuel_multiplier
import config

def find_pure_rules(days=700, symbol="XAUUSD.iux"):
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

    records = []
    for i in range(100, len(rates) - 10):
        current_bar = df_master.iloc[i]; prev_bar = df_master.iloc[i - 1]
        if pd.isna(current_bar['atr']) or pd.isna(current_bar['rsi']) or pd.isna(current_bar['ema_200']): continue
        
        lookback_bars = df_master.iloc[i - 14 : i - 3]
        local_low = lookback_bars['low'].min(); local_high = lookback_bars['high'].max()
        active_mode = getattr(config, "S20_13_ACTIVE_MODE", 2.6)
        target_tf_buy = getattr(config, "S20_13_TARGET_TF_BUY", "H12")
        hour = current_bar['time_dt'].hour
        
        is_ny_pre_open = (hour in [12, 13]); is_sydney_open = (hour in [23, 0]); is_tokyo_buy = (hour == 2)
        is_late_ny_buy = (hour == 19); is_midnight_buy = (hour == 17); is_london_open = (hour == 8); is_london_fake = (hour == 9)
        
        cur_range = current_bar['high'] - current_bar['low']
        is_strong_range = cur_range >= (0.8 * current_bar['atr'])
        if not is_strong_range: continue
        
        recent_3 = df_master.iloc[i-2:i+1]
        sweep_buy = recent_3['low'].min() < local_low; engulf_buy = current_bar['close'] > prev_bar['high']
        instant_sweep_buy = current_bar['low'] < local_low and current_bar['close'] > prev_bar['high']
        
        sig = None
        if (sweep_buy and engulf_buy) or instant_sweep_buy:
            if not (is_ny_pre_open or is_sydney_open or is_tokyo_buy or is_late_ny_buy or is_midnight_buy or is_london_open or is_london_fake):
                sig = "BUY"
                entry = current_bar['close']
                sweep_bottom = min(recent_3['low'].min(), current_bar['low'])
                sl = sweep_bottom - config.SL_BUFFER(current_bar['atr'])
                tp = sweep_bottom + (current_bar['atr'] * active_mode * get_fuel_multiplier("H1", target_tf_buy))
                
        if sig == "BUY":
            res = evaluate_bar(df_master, i, tf="H1")
            is_v23_pass = (res and res.get("signal") == "BUY")
            if is_v23_pass: continue
            
            reason = res.get("reason", "Unknown")
            clean_reason = re.sub(r'\(.*?\)', '', reason).strip()
            
            future_rates = rates[i+1:]
            be_trig = entry + ((tp - entry) * 0.4)
            be_act = False; closed_type = None
            for f_bar in future_rates:
                if f_bar['low'] <= sl: closed_type = "BE" if be_act else "LOSS"; break
                elif f_bar['high'] >= tp: closed_type = "WIN"; break
                if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
            
            if closed_type in ["WIN", "LOSS"]:
                records.append({
                    "time": current_bar['time_dt'].strftime("%Y-%m-%d %H"),
                    "category": clean_reason, "outcome": closed_type,
                    "rsi": current_bar['rsi'], "adx": current_bar['adx'],
                    "di_diff": current_bar['di_diff'], "vol_ratio": current_bar['vol_ratio'],
                    "z_score": current_bar['z_score'], "atr_pct": current_bar['atr_pct'],
                    "dist_ema50": current_bar['dist_ema50'], "hour": hour
                })

    df = pd.DataFrame(records)

    print("--- 1. DRIFT BLOCK PURE RULES (Loss <= 1) ---")
    drift = df[df['category'] == 'BUY Low Volatility Drift Block']
    d_res = []
    for min_di in [-10, -5, 0, 5, 10]:
        for min_vol in [0.8, 1.0, 1.2, 1.5, 2.0]:
            for min_z in [0.0, 0.5, 1.0, 1.5, 2.0]:
                for min_adx in [10, 15, 20]:
                    sub = drift[(drift['di_diff'] >= min_di) & (drift['vol_ratio'] >= min_vol) & (drift['z_score'] >= min_z) & (drift['adx'] >= min_adx)]
                    w = len(sub[sub['outcome'] == 'WIN']); l = len(sub[sub['outcome'] == 'LOSS'])
                    if w >= 5 and l <= 1:
                        d_res.append((w, l, f"di>={min_di}, vol>={min_vol}, z>={min_z}, adx>={min_adx}"))
    d_res.sort(key=lambda x: (x[0], -x[1]), reverse=True)
    for r in d_res[:10]: print(f"Wins: {r[0]} | Losses: {r[1]} | Rule: {r[2]}")

    print("\n--- 2. TREND/Z BLOCK PURE RULES (Loss <= 1) ---")
    tz = df[df['category'] == 'BUY Trend/Z Block']
    tz_res = []
    for min_di in [-5, 0, 5]:
        for max_adx in [35, 40, 50, 60]:
            for min_vol in [0.8, 1.2, 1.5, 2.0]:
                for min_z in [0.0, 0.5, 1.0]:
                    sub = tz[(tz['di_diff'] >= min_di) & (tz['adx'] <= max_adx) & (tz['vol_ratio'] >= min_vol) & (tz['z_score'] >= min_z)]
                    w = len(sub[sub['outcome'] == 'WIN']); l = len(sub[sub['outcome'] == 'LOSS'])
                    if w >= 3 and l <= 1:
                        tz_res.append((w, l, f"di>={min_di}, adx<={max_adx}, vol>={min_vol}, z>={min_z}"))
    tz_res.sort(key=lambda x: (x[0], -x[1]), reverse=True)
    for r in tz_res[:10]: print(f"Wins: {r[0]} | Losses: {r[1]} | Rule: {r[2]}")

    print("\n--- 3. RSI LOW BLOCK PURE RULES (Loss <= 1) ---")
    rsi_low = df[df['category'] == 'RSI too low']
    r_res = []
    for max_adx in [40, 50, 60]:
        for min_di in [-35, -25, -15, -5]:
            for min_vol in [0.5, 0.8, 1.0, 1.2]:
                for max_rsi in [33, 35]:
                    sub = rsi_low[(rsi_low['adx'] <= max_adx) & (rsi_low['di_diff'] >= min_di) & (rsi_low['vol_ratio'] >= min_vol) & (rsi_low['rsi'] <= max_rsi)]
                    w = len(sub[sub['outcome'] == 'WIN']); l = len(sub[sub['outcome'] == 'LOSS'])
                    if w >= 3 and l <= 1:
                        r_res.append((w, l, f"adx<={max_adx}, di>={min_di}, vol>={min_vol}, rsi<={max_rsi}"))
    r_res.sort(key=lambda x: (x[0], -x[1]), reverse=True)
    for r in r_res[:10]: print(f"Wins: {r[0]} | Losses: {r[1]} | Rule: {r[2]}")

    mt5.shutdown()

if __name__ == "__main__":
    find_pure_rules()
