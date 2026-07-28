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

def print_step1(days=700, symbol="XAUUSD.iux", compound=1.5):
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
            
            # Check Step 1 unlock conditions
            is_unlocked = False
            if clean_reason == "BUY Low Volatility Drift Block":
                if current_bar['di_diff'] > -3.0 and current_bar['vol_ratio'] > 1.15 and current_bar['z_score'] > 0.05 and hour not in [7, 10, 11]:
                    is_unlocked = True
            elif clean_reason == "BUY Trend/Z Block":
                if current_bar['di_diff'] > -1.0 and current_bar['adx'] < 37.0 and hour not in [10, 15, 16]:
                    is_unlocked = True
                    
            if not is_unlocked: continue
            
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
                    "rsi": round(current_bar['rsi'], 1), "adx": round(current_bar['adx'], 1),
                    "di_diff": round(current_bar['di_diff'], 1), "vol_ratio": round(current_bar['vol_ratio'], 2),
                    "z_score": round(current_bar['z_score'], 2), "atr_pct": round(current_bar['atr_pct'], 2),
                    "dist_ema50": round(current_bar['dist_ema50'], 1), "hour": hour
                })

    df = pd.DataFrame(records)
    print(df.to_string(index=False))

    mt5.shutdown()

if __name__ == "__main__":
    print_step1()
