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

def simulate_v24(days=700, symbol="XAUUSD.iux", compound=1.5):
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

    wins = 0; losses = 0; be = 0; trades = 0; pnl = 0.0
    sl_buy_count = 0; sl_sell_count = 0
    last_buy_loss = -99999.0; last_sell_loss = -99999.0
    master_dates = {"2026-07-16 16:00": False, "2026-07-17 14:00": False, "2026-07-17 16:00": False}

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
                
        if not sig: continue
        
        res = evaluate_bar(df_master, i, tf="H1")
        is_v23_pass = (res and res.get("signal") == sig)
        reason = res.get("reason", "") if res else ""
        clean_reason = re.sub(r'\(.*?\)', '', reason).strip()
        
        final_signal = None
        if is_v23_pass:
            final_signal = sig
        else:
            # V24 Zero-Loss Unlocks
            if sig == "BUY" and clean_reason == "BUY Low Volatility Drift Block":
                if current_bar['di_diff'] >= 5.0 and current_bar['vol_ratio'] >= 1.0 and current_bar['z_score'] >= 1.0 and current_bar['adx'] >= 15.0:
                    final_signal = "BUY"
            elif sig == "BUY" and clean_reason == "BUY Trend/Z Block":
                if current_bar['di_diff'] >= 0.0 and current_bar['adx'] <= 50.0 and current_bar['vol_ratio'] >= 1.5 and current_bar['z_score'] >= 0.0:
                    final_signal = "BUY"
            elif sig == "BUY" and clean_reason == "BUY Trend Exhaustion Block":
                if current_bar['adx'] > 50.0 and current_bar['vol_ratio'] > 1.2 and current_bar['z_score'] < -0.1:
                    final_signal = "BUY"
                    
        if not final_signal: continue
        
        # Deduplication
        if final_signal == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
        if final_signal == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
        
        t_str = current_bar['time_dt'].strftime("%Y-%m-%d %H:%M")
        if t_str in master_dates: master_dates[t_str] = True
        
        future_rates = rates[i+1:]
        be_trig = entry + ((tp - entry) * 0.4) if final_signal == "BUY" else entry - ((entry - tp) * 0.4)
        be_act = False
        for f_bar in future_rates:
            if final_signal == "BUY":
                if f_bar['low'] <= sl:
                    if be_act: be += 1
                    else:
                        losses += 1; pnl -= ((entry - sl) * 10 * compound); sl_buy_count += 1; last_buy_loss = entry
                    trades += 1; break
                elif f_bar['high'] >= tp:
                    wins += 1; trades += 1; sl_buy_count = 0; pnl += ((tp - entry) * 10 * compound)
                    break
                if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
            elif final_signal == "SELL":
                if f_bar['high'] >= sl:
                    if be_act: be += 1
                    else:
                        losses += 1; pnl -= ((sl - entry) * 10 * compound); sl_sell_count += 1; last_sell_loss = entry
                    trades += 1; break
                elif f_bar['low'] <= tp:
                    wins += 1; trades += 1; sl_sell_count = 0; pnl += ((entry - tp) * 10 * compound)
                    break
                if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry

    print("=========================================================")
    print(f"V24 Official Simulation Results (Compound={compound}):")
    print(f"Wins: {wins} | Losses: {losses} | BE: {be} | Total: {trades}")
    wr_wl = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
    print(f"Win Rate (W/L): {wr_wl:.2f}%")
    print(f"Net Profit: ${pnl:,.2f}")
    print(f"Master Dates (UTC): {master_dates}")
    print("=========================================================")

    mt5.shutdown()

if __name__ == "__main__":
    simulate_v24()
