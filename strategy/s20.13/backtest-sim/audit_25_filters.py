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

def audit_filters(days=700, symbol="XAUUSD.iux", compound=1.5):
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

    def eval_with_bypass(df, idx, tf="H1", bypass_rule=None):
        if idx < 20 or idx >= len(df): return {"signal": "WAIT"}
        current_bar = df.iloc[idx]; prev_bar = df.iloc[idx - 1]
        if pd.isna(current_bar['atr']) or pd.isna(current_bar['rsi']) or pd.isna(current_bar['ema_200']): return {"signal": "WAIT"}
        
        lookback_bars = df.iloc[idx - 14 : idx - 3]
        local_low = lookback_bars['low'].min(); local_high = lookback_bars['high'].max()
        active_mode = getattr(config, "S20_13_ACTIVE_MODE", 2.6)
        target_tf_buy = getattr(config, "S20_13_TARGET_TF_BUY", "H12")
        target_tf_sell = getattr(config, "S20_13_TARGET_TF_SELL", "D1")
        hour = current_bar['time_dt'].hour
        
        is_ny_pre_open = (hour in [12, 13]); is_sydney_open = (hour in [23, 0]); is_tokyo_buy = (hour == 2)
        is_late_ny_buy = (hour == 19); is_midnight_buy = (hour == 17); is_london_open = (hour == 8); is_london_fake = (hour == 9)
        
        cur_range = current_bar['high'] - current_bar['low']
        is_strong_range = cur_range >= (0.8 * current_bar['atr'])
        
        recent_3 = df.iloc[idx-2:idx+1]
        sweep_buy = recent_3['low'].min() < local_low; engulf_buy = current_bar['close'] > prev_bar['high']
        instant_sweep_buy = current_bar['low'] < local_low and current_bar['close'] > prev_bar['high']
        
        if (sweep_buy and engulf_buy) or instant_sweep_buy:
            if not is_strong_range or is_ny_pre_open or is_sydney_open or is_tokyo_buy or is_late_ny_buy or is_midnight_buy or is_london_open or is_london_fake:
                return {"signal": "WAIT"}
            if bypass_rule != "buy_rsi_min" and current_bar['rsi'] < 35: return {"signal": "WAIT"}
            if bypass_rule != "buy_trend_z" and current_bar['z_score'] > 0.0 and current_bar['adx'] > 30.0: return {"signal": "WAIT"}
            if bypass_rule != "buy_trend_exh" and current_bar['adx'] > 52.0: return {"signal": "WAIT"}
            if bypass_rule != "buy_low_vol" and current_bar['atr_pct'] <= 0.41 and current_bar['adx'] < 50.0: return {"signal": "WAIT"}
            if bypass_rule != "buy_vol_ratio" and current_bar['vol_ratio'] < 0.55: return {"signal": "WAIT"}
            if bypass_rule != "buy_rsi_dist50" and current_bar['rsi'] > 40.0 and current_bar['dist_ema50'] < -20.0: return {"signal": "WAIT"}
            if bypass_rule != "buy_rsi_di" and current_bar['rsi'] < 48.0 and current_bar['di_diff'] > 0.0: return {"signal": "WAIT"}
            if bypass_rule != "buy_rsi_adx" and current_bar['rsi'] < 40.0 and current_bar['adx'] > 42.0: return {"signal": "WAIT"}
            
            sweep_bottom = min(recent_3['low'].min(), current_bar['low'])
            sl = sweep_bottom - config.SL_BUFFER(current_bar['atr'])
            fuel = current_bar['atr'] * active_mode * get_fuel_multiplier("H1", target_tf_buy)
            return {"signal": "BUY", "entry": current_bar['close'], "sl": sl, "tp": sweep_bottom + fuel}
            
        sweep_sell = recent_3['high'].max() > local_high; engulf_sell = current_bar['close'] < prev_bar['low']
        instant_sweep_sell = current_bar['high'] > local_high and current_bar['close'] < prev_bar['low']
        
        if (sweep_sell and engulf_sell) or instant_sweep_sell:
            if not is_strong_range or is_ny_pre_open or is_sydney_open or is_london_open or is_london_fake:
                return {"signal": "WAIT"}
            if bypass_rule != "sell_rsi_max" and current_bar['rsi'] > 60: return {"signal": "WAIT"}
            if bypass_rule != "sell_z_adx" and ((current_bar['z_score'] < 0.0 and current_bar['adx'] > 50.0) or (current_bar['close'] - current_bar['ema_50'] > 100.0)): return {"signal": "WAIT"}
            if bypass_rule != "sell_mom_conf" and current_bar['rsi_7'] > 50.5 and 0.35 <= current_bar['body_pct'] <= 0.615: return {"signal": "WAIT"}
            if bypass_rule != "sell_mom_conf2" and current_bar['rsi_7'] > 50.5 and 0.35 <= current_bar['body_pct'] <= 0.65 and current_bar['di_diff'] < 4.0: return {"signal": "WAIT"}
            if bypass_rule != "sell_vol_di" and current_bar['vol_ratio'] < 0.88 and current_bar['di_diff'] > 1.0: return {"signal": "WAIT"}
            if bypass_rule != "sell_body_min" and current_bar['body_pct'] < 0.145: return {"signal": "WAIT"}
            if bypass_rule != "sell_oversold_trap" and current_bar['rsi'] < 37.0 and current_bar['z_score'] > -1.80: return {"signal": "WAIT"}
            if bypass_rule != "sell_low_adx" and current_bar['adx'] < 17.5 and current_bar['vol_ratio'] < 0.90: return {"signal": "WAIT"}
            if bypass_rule != "sell_rsi_div" and current_bar['rsi'] > 58.5 and current_bar['rsi_7'] < 41.5: return {"signal": "WAIT"}
            if bypass_rule != "sell_rsi7_di" and current_bar['rsi_7'] < 41.5 and current_bar['di_diff'] > 0.5: return {"signal": "WAIT"}
            if bypass_rule != "sell_adx_dist" and current_bar['adx'] < 20.2 and (current_bar['close'] - current_bar['ema_50']) > -12.0: return {"signal": "WAIT"}
            if bypass_rule != "sell_vol_rsi" and current_bar['vol_ratio'] < 1.90 and current_bar['rsi'] < 39.0: return {"signal": "WAIT"}
            if bypass_rule != "sell_z_atr" and current_bar['z_score'] > 0.20 and current_bar['atr_pct'] < 0.31: return {"signal": "WAIT"}
            if bypass_rule != "sell_rsi_rsi7" and current_bar['rsi'] > 53.0 and current_bar['rsi_7'] < 37.0: return {"signal": "WAIT"}
            if bypass_rule != "sell_dist_wick" and current_bar['dist_ema50'] > 20.0 and current_bar['upper_wick_pct'] > 0.15: return {"signal": "WAIT"}
            if bypass_rule != "sell_hour10" and hour == 10: return {"signal": "WAIT"}
            if bypass_rule != "sell_adx_vol" and current_bar['adx'] > 20.0 and current_bar['vol_ratio'] > 2.50: return {"signal": "WAIT"}
            if bypass_rule != "sell_adx_lwick" and current_bar['adx'] < 25.0 and current_bar['lower_wick_pct'] > 0.40: return {"signal": "WAIT"}
            if bypass_rule != "sell_di_dist" and current_bar['di_diff'] < 0.0 and current_bar['dist_ema50'] > 20.0: return {"signal": "WAIT"}
            if bypass_rule != "sell_dist50_200" and current_bar['dist_ema50'] < 10.0 and current_bar['dist_ema200'] > 50.0: return {"signal": "WAIT"}
            if bypass_rule != "sell_rsi_di_neg" and current_bar['rsi'] > 55.0 and current_bar['di_diff'] < -3.0: return {"signal": "WAIT"}
            if bypass_rule != "sell_rsi_di_pos" and current_bar['rsi'] > 58.0 and current_bar['di_diff'] > 10.0: return {"signal": "WAIT"}
            if bypass_rule != "sell_rsi_dist200" and current_bar['rsi'] < 50.0 and current_bar['dist_ema200'] > 80.0: return {"signal": "WAIT"}
            if bypass_rule != "sell_z_wick" and current_bar['z_score'] < -1.50 and current_bar['upper_wick_pct'] > 0.30: return {"signal": "WAIT"}
            if bypass_rule != "sell_body_atr" and current_bar['body_pct'] > 0.70 and current_bar['atr_pct'] < 0.30: return {"signal": "WAIT"}
            if bypass_rule != "sell_rsi_z" and current_bar['rsi'] < 52.0 and current_bar['z_score'] > 0.0: return {"signal": "WAIT"}
            if bypass_rule != "sell_rsi7_body" and current_bar['rsi_7'] < 55.0 and current_bar['body_pct'] > 0.90: return {"signal": "WAIT"}
            
            sweep_top = max(recent_3['high'].max(), current_bar['high'])
            sl = sweep_top + config.SL_BUFFER(current_bar['atr'])
            fuel = current_bar['atr'] * active_mode * get_fuel_multiplier("H1", target_tf_sell)
            return {"signal": "SELL", "entry": current_bar['close'], "sl": sl, "tp": sweep_top - fuel}
            
        return {"signal": "WAIT"}

    rules = [None, "buy_trend_z", "buy_trend_exh", "buy_low_vol", "buy_rsi_dist50", "buy_rsi_di", "buy_rsi_adx",
             "sell_rsi_max", "sell_z_adx", "sell_mom_conf", "sell_mom_conf2", "sell_vol_di", "sell_oversold_trap",
             "sell_rsi_div", "sell_rsi7_di", "sell_adx_dist", "sell_vol_rsi", "sell_z_atr", "sell_dist_wick",
             "sell_hour10", "sell_adx_vol", "sell_adx_lwick", "sell_di_dist", "sell_dist50_200", "sell_rsi_di_neg",
             "sell_rsi_di_pos", "sell_rsi_dist200", "sell_z_wick", "sell_body_atr", "sell_rsi_z", "sell_rsi7_body"]

    for rule in rules:
        wins, losses, be, trades, pnl = 0, 0, 0, 0, 0.0
        sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
        for i in range(100, len(rates) - 10):
            res = eval_with_bypass(df_master, i, tf="H1", bypass_rule=rule)
            if res and res.get("signal") in ["BUY", "SELL"]:
                signal = res["signal"]; entry = res["entry"]; sl = res["sl"]; tp = res["tp"]
                if signal == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
                if signal == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
                future_rates = rates[i+1:]
                be_trig = entry + ((tp - entry) * 0.4) if signal == "BUY" else entry - ((entry - tp) * 0.4)
                be_act = False
                for f_bar in future_rates:
                    if signal == "BUY":
                        if f_bar['low'] <= sl:
                            if be_act: be += 1
                            else: losses += 1; pnl -= ((entry - sl) * 10 * compound); sl_buy_count += 1; last_buy_loss = entry
                            trades += 1; break
                        elif f_bar['high'] >= tp:
                            wins += 1; trades += 1; sl_buy_count = 0; pnl += ((tp - entry) * 10 * compound); break
                        if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                    elif signal == "SELL":
                        if f_bar['high'] >= sl:
                            if be_act: be += 1
                            else: losses += 1; pnl -= ((sl - entry) * 10 * compound); sl_sell_count += 1; last_sell_loss = entry
                            trades += 1; break
                        elif f_bar['low'] <= tp:
                            wins += 1; trades += 1; sl_sell_count = 0; pnl += ((entry - tp) * 10 * compound); break
                        if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry
        win_rate_wl = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        r_name = str(rule) if rule else "BASELINE (No Bypass)"
        print(f"{r_name:<20} | Wins: {wins:3d} | Losses: {losses:2d} | BE: {be:2d} | WR: {win_rate_wl:6.2f}% | PnL: ${pnl:11,.2f}")

    mt5.shutdown()

if __name__ == "__main__":
    audit_filters()
