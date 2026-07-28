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

def grid_search_unlock(days=700, symbol="XAUUSD.iux", compound=1.5):
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
        target_tf_sell = getattr(config, "S20_13_TARGET_TF_SELL", "D1")
        hour = current_bar['time_dt'].hour
        
        is_ny_pre_open = (hour in [12, 13]); is_sydney_open = (hour in [23, 0]); is_tokyo_buy = (hour == 2)
        is_late_ny_buy = (hour == 19); is_midnight_buy = (hour == 17); is_london_open = (hour == 8); is_london_fake = (hour == 9)
        
        cur_range = current_bar['high'] - current_bar['low']
        is_strong_range = cur_range >= (0.8 * current_bar['atr'])
        if not is_strong_range: continue
        
        recent_3 = df_master.iloc[i-2:i+1]
        sweep_buy = recent_3['low'].min() < local_low; engulf_buy = current_bar['close'] > prev_bar['high']
        instant_sweep_buy = current_bar['low'] < local_low and current_bar['close'] > prev_bar['high']
        
        sweep_sell = recent_3['high'].max() > local_high; engulf_sell = current_bar['close'] < prev_bar['low']
        instant_sweep_sell = current_bar['high'] > local_high and current_bar['close'] < prev_bar['low']
        
        sig = None
        if (sweep_buy and engulf_buy) or instant_sweep_buy:
            if not (is_ny_pre_open or is_sydney_open or is_tokyo_buy or is_late_ny_buy or is_midnight_buy or is_london_open or is_london_fake):
                sig = "BUY"
                entry = current_bar['close']
                sweep_bottom = min(recent_3['low'].min(), current_bar['low'])
                sl = sweep_bottom - config.SL_BUFFER(current_bar['atr'])
                tp = sweep_bottom + (current_bar['atr'] * active_mode * get_fuel_multiplier("H1", target_tf_buy))
        elif (sweep_sell and engulf_sell) or instant_sweep_sell:
            if not (is_ny_pre_open or is_sydney_open or is_london_open or is_london_fake):
                sig = "SELL"
                entry = current_bar['close']
                sweep_top = max(recent_3['high'].max(), current_bar['high'])
                sl = sweep_top + config.SL_BUFFER(current_bar['atr'])
                tp = sweep_top - (current_bar['atr'] * active_mode * get_fuel_multiplier("H1", target_tf_sell))
                
        if sig:
            res = evaluate_bar(df_master, i, tf="H1")
            is_v23_pass = (res and res.get("signal") == sig)
            if is_v23_pass:
                records.append({"idx": i, "sig": sig, "entry": entry, "sl": sl, "tp": tp, "status": "V23_PASS", "category": "V23_PASS"})
                continue
                
            reason = res.get("reason", "Unknown")
            clean_reason = re.sub(r'\(.*?\)', '', reason).strip()
            
            future_rates = rates[i+1:]
            be_trig = entry + ((tp - entry) * 0.4) if sig == "BUY" else entry - ((entry - tp) * 0.4)
            be_act = False; closed_type = None
            for f_bar in future_rates:
                if sig == "BUY":
                    if f_bar['low'] <= sl: closed_type = "BE" if be_act else "LOSS"; break
                    elif f_bar['high'] >= tp: closed_type = "WIN"; break
                    if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                elif sig == "SELL":
                    if f_bar['high'] >= sl: closed_type = "BE" if be_act else "LOSS"; break
                    elif f_bar['low'] <= tp: closed_type = "WIN"; break
                    if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry
            
            if closed_type in ["WIN", "LOSS"]:
                records.append({
                    "idx": i, "sig": sig, "entry": entry, "sl": sl, "tp": tp, "status": closed_type, "category": clean_reason,
                    "rsi": current_bar['rsi'], "adx": current_bar['adx'], "di_diff": current_bar['di_diff'],
                    "vol_ratio": current_bar['vol_ratio'], "z_score": current_bar['z_score'],
                    "atr_pct": current_bar['atr_pct'], "dist_ema50": current_bar['dist_ema50'],
                    "body_pct": current_bar['body_pct'], "hour": hour
                })

    df = pd.DataFrame(records)
    print(f"Total V23 PASS: {len(df[df['status'] == 'V23_PASS'])}")
    
    # Grid search for BUY Low Volatility Drift Block
    drift = df[df['category'] == 'BUY Low Volatility Drift Block']
    print("\n--- Testing Drift Block Unlocks ---")
    best_d_wins, best_d_loss, best_d_cond = 0, 999, ""
    for min_di in [-5, -2, 0, 2]:
        for min_vol in [1.0, 1.1, 1.2, 1.3]:
            for min_z in [0.0, 0.1, 0.2]:
                sub = drift[(drift['di_diff'] > min_di) & (drift['vol_ratio'] > min_vol) & (drift['z_score'] > min_z) & (~drift['hour'].isin([6, 10, 11]))]
                w = len(sub[sub['status'] == 'WIN']); l = len(sub[sub['status'] == 'LOSS'])
                if w >= best_d_wins and l <= 1:
                    best_d_wins = w; best_d_loss = l; best_d_cond = f"di > {min_di}, vol > {min_vol}, z > {min_z}"
    print(f"Best Drift Unlock: {best_d_wins} Wins | {best_d_loss} Losses | Cond: {best_d_cond}")

    # Grid search for BUY Trend/Z Block
    tz = df[df['category'] == 'BUY Trend/Z Block']
    print("\n--- Testing Trend/Z Block Unlocks ---")
    best_tz_wins, best_tz_loss, best_tz_cond = 0, 999, ""
    for min_di in [-2, 0, 2, 5]:
        for max_adx in [35, 38, 40]:
            for min_vol in [1.1, 1.2, 1.5]:
                sub = tz[(tz['di_diff'] > min_di) & (tz['adx'] < max_adx) & (tz['vol_ratio'] > min_vol) & (~tz['hour'].isin([6, 10, 15, 16]))]
                w = len(sub[sub['status'] == 'WIN']); l = len(sub[sub['status'] == 'LOSS'])
                if w >= best_tz_wins and l <= 1:
                    best_tz_wins = w; best_tz_loss = l; best_tz_cond = f"di > {min_di}, adx < {max_adx}, vol > {min_vol}"
    print(f"Best Trend/Z Unlock: {best_tz_wins} Wins | {best_tz_loss} Losses | Cond: {best_tz_cond}")

    # Grid search for RSI too low
    rsi_low = df[df['category'] == 'RSI too low']
    print("\n--- Testing RSI Low Unlocks ---")
    best_r_wins, best_r_loss, best_r_cond = 0, 999, ""
    for max_adx in [40, 45, 50]:
        for min_di in [-25, -20, -15]:
            for min_vol in [0.8, 0.9, 1.0]:
                sub = rsi_low[(rsi_low['adx'] < max_adx) & (rsi_low['di_diff'] > min_di) & (rsi_low['vol_ratio'] > min_vol) & (~rsi_low['hour'].isin([6, 15, 16, 18]))]
                w = len(sub[sub['status'] == 'WIN']); l = len(sub[sub['status'] == 'LOSS'])
                if w >= best_r_wins and l <= 1:
                    best_r_wins = w; best_r_loss = l; best_r_cond = f"adx < {max_adx}, di > {min_di}, vol > {min_vol}"
    print(f"Best RSI Low Unlock: {best_r_wins} Wins | {best_r_loss} Losses | Cond: {best_r_cond}")

    mt5.shutdown()

if __name__ == "__main__":
    grid_search_unlock()
