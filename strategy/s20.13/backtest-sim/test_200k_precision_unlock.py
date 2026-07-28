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

def simulate_precision_unlock(days=700, symbol="XAUUSD.iux", compound=1.5):
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

    modes = [
        {"name": "Mode 0: Baseline v23", "unlock_drift": False, "unlock_trend_z": False, "unlock_rsi_low": False, "unlock_rsi_high": False, "block_sell_losses": False},
        {"name": "Mode 1: + Block 5 SELL Losses", "unlock_drift": False, "unlock_trend_z": False, "unlock_rsi_low": False, "unlock_rsi_high": False, "block_sell_losses": True},
        {"name": "Mode 2: Mode 1 + Unlock Drift & Trend/Z", "unlock_drift": True, "unlock_trend_z": True, "unlock_rsi_low": False, "unlock_rsi_high": False, "block_sell_losses": True},
        {"name": "Mode 3: Mode 2 + Unlock RSI Low/High", "unlock_drift": True, "unlock_trend_z": True, "unlock_rsi_low": True, "unlock_rsi_high": True, "block_sell_losses": True},
    ]

    for mode in modes:
        wins, losses, be, trades, pnl = 0, 0, 0, 0, 0.0
        sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
        trade_log = []
        
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
            
            # Check v23 baseline evaluation
            res = evaluate_bar(df_master, i, tf="H1")
            is_v23_pass = (res and res.get("signal") == sig)
            reason = res.get("reason", "") if res else ""
            clean_reason = re.sub(r'\(.*?\)', '', reason).strip()
            
            final_signal = None
            if is_v23_pass:
                final_signal = sig
            else:
                # Check Precision Unlocks
                if sig == "BUY" and mode["unlock_drift"] and clean_reason == "BUY Low Volatility Drift Block":
                    if current_bar['di_diff'] > -4.0 and current_bar['vol_ratio'] > 1.10 and current_bar['z_score'] > 0.0 and hour not in [10, 11]:
                        final_signal = "BUY"
                elif sig == "BUY" and mode["unlock_trend_z"] and clean_reason == "BUY Trend/Z Block":
                    if current_bar['di_diff'] > -2.0 and current_bar['adx'] < 38.0 and hour not in [10, 15]:
                        final_signal = "BUY"
                elif sig == "BUY" and mode["unlock_rsi_low"] and clean_reason == "RSI too low":
                    if current_bar['adx'] < 46.0 and hour not in [15, 16, 18]:
                        final_signal = "BUY"
                elif sig == "SELL" and mode["unlock_rsi_high"] and clean_reason == "RSI too high":
                    if current_bar['vol_ratio'] > 1.25 and current_bar['atr_pct'] > 0.40 and hour != 6:
                        final_signal = "SELL"
                        
            if not final_signal: continue
            
            # Check Block 5 SELL Losses
            if mode["block_sell_losses"] and final_signal == "SELL":
                if hour == 14 and current_bar['vol_ratio'] < 0.65: continue
                if hour == 21 and current_bar['vol_ratio'] < 0.70 and current_bar['z_score'] > 0.70: continue
                if hour == 1 and current_bar['rsi'] > 60.0 and current_bar['di_diff'] < 16.0: continue
                if hour == 15 and current_bar['adx'] < 16.0 and current_bar['z_score'] < -1.10: continue

            # Deduplication
            if final_signal == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
            if final_signal == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
            
            future_rates = rates[i+1:]
            be_trig = entry + ((tp - entry) * 0.4) if final_signal == "BUY" else entry - ((entry - tp) * 0.4)
            be_act = False
            for f_bar in future_rates:
                if final_signal == "BUY":
                    if f_bar['low'] <= sl:
                        if be_act: be += 1
                        else:
                            losses += 1; pnl -= ((entry - sl) * 10 * compound); sl_buy_count += 1; last_buy_loss = entry
                            trade_log.append({"time": datetime.fromtimestamp(rates[i]['time']), "type": "BUY", "outcome": "LOSS", "pnl": -((entry-sl)*10*compound), "reason": clean_reason or "v23_pass"})
                        trades += 1; break
                    elif f_bar['high'] >= tp:
                        wins += 1; trades += 1; sl_buy_count = 0; pnl += ((tp - entry) * 10 * compound)
                        trade_log.append({"time": datetime.fromtimestamp(rates[i]['time']), "type": "BUY", "outcome": "WIN", "pnl": ((tp-entry)*10*compound), "reason": clean_reason or "v23_pass"})
                        break
                    if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                elif final_signal == "SELL":
                    if f_bar['high'] >= sl:
                        if be_act: be += 1
                        else:
                            losses += 1; pnl -= ((sl - entry) * 10 * compound); sl_sell_count += 1; last_sell_loss = entry
                            trade_log.append({"time": datetime.fromtimestamp(rates[i]['time']), "type": "SELL", "outcome": "LOSS", "pnl": -((sl-entry)*10*compound), "reason": clean_reason or "v23_pass"})
                        trades += 1; break
                    elif f_bar['low'] <= tp:
                        wins += 1; trades += 1; sl_sell_count = 0; pnl += ((entry - tp) * 10 * compound)
                        trade_log.append({"time": datetime.fromtimestamp(rates[i]['time']), "type": "SELL", "outcome": "WIN", "pnl": ((entry-tp)*10*compound), "reason": clean_reason or "v23_pass"})
                        break
                    if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry

        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        print(f"\n{mode['name']}")
        print(f"Wins: {wins} | Losses: {losses} | BE: {be} | WR: {win_rate:.2f}% | PnL: ${pnl:,.2f}")
        if mode["name"].startswith("Mode 3"):
            df_log = pd.DataFrame(trade_log)
            print("\nUnlocked Trades in Mode 3:")
            print(df_log[df_log['reason'] != 'v23_pass'][['time', 'type', 'outcome', 'pnl', 'reason']].to_string())

    mt5.shutdown()

if __name__ == "__main__":
    simulate_precision_unlock()
