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

def optimize_200k(days=700, symbol="XAUUSD.iux", compound=1.5):
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

    def get_raw_pa_signal(df, idx):
        if idx < 20 or idx >= len(df): return None, None, None, None
        current_bar = df.iloc[idx]; prev_bar = df.iloc[idx - 1]
        if pd.isna(current_bar['atr']) or pd.isna(current_bar['rsi']) or pd.isna(current_bar['ema_200']): return None, None, None, None
        
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
        if not is_strong_range: return None, None, None, None
        
        recent_3 = df.iloc[idx-2:idx+1]
        sweep_buy = recent_3['low'].min() < local_low; engulf_buy = current_bar['close'] > prev_bar['high']
        instant_sweep_buy = current_bar['low'] < local_low and current_bar['close'] > prev_bar['high']
        
        sweep_sell = recent_3['high'].max() > local_high; engulf_sell = current_bar['close'] < prev_bar['low']
        instant_sweep_sell = current_bar['high'] > local_high and current_bar['close'] < prev_bar['low']
        
        if (sweep_buy and engulf_buy) or instant_sweep_buy:
            if not (is_ny_pre_open or is_sydney_open or is_tokyo_buy or is_late_ny_buy or is_midnight_buy or is_london_open or is_london_fake):
                sweep_bottom = min(recent_3['low'].min(), current_bar['low'])
                sl = sweep_bottom - config.SL_BUFFER(current_bar['atr'])
                tp = sweep_bottom + (current_bar['atr'] * active_mode * get_fuel_multiplier("H1", target_tf_buy))
                return "BUY", current_bar['close'], sl, tp
        elif (sweep_sell and engulf_sell) or instant_sweep_sell:
            if not (is_ny_pre_open or is_sydney_open or is_london_open or is_london_fake):
                sweep_top = max(recent_3['high'].max(), current_bar['high'])
                sl = sweep_top + config.SL_BUFFER(current_bar['atr'])
                tp = sweep_top - (current_bar['atr'] * active_mode * get_fuel_multiplier("H1", target_tf_sell))
                return "SELL", current_bar['close'], sl, tp
        return None, None, None, None

    def eval_candidate(df, idx, step_mode=0):
        res = evaluate_bar(df, idx, tf="H1")
        if res and res.get("signal") in ["BUY", "SELL"]:
            # Baseline v23 pass
            return res
            
        if step_mode == 0: return res
        
        # Check if raw PA is valid
        sig, entry, sl, tp = get_raw_pa_signal(df, idx)
        if not sig: return res
        
        cur = df.iloc[idx]
        hour = cur['time_dt'].hour
        reason = res.get("reason", "") if res else ""
        clean_reason = re.sub(r'\(.*?\)', '', reason).strip()
        
        # Step Mode 1: Unlock High-Confidence Drift & Trend/Z (BUY)
        if sig == "BUY" and clean_reason == "BUY Low Volatility Drift Block":
            # From mining: di_diff > -4, vol_ratio > 1.10, z_score > 0, hour not in [10, 11]
            if cur['di_diff'] > -3.0 and cur['vol_ratio'] > 1.15 and cur['z_score'] > 0.05 and hour not in [7, 10, 11]:
                return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "reason": "v24 Unlocked Drift"}
        if sig == "BUY" and clean_reason == "BUY Trend/Z Block":
            if cur['di_diff'] > -1.0 and cur['adx'] < 37.0 and hour not in [10, 15, 16]:
                return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "reason": "v24 Unlocked Trend/Z"}
                
        if step_mode == 1: return res
        
        # Step Mode 2: Step 1 + Unlock Oversold BUY & Overbought SELL
        if sig == "BUY" and clean_reason == "RSI too low":
            if cur['adx'] < 44.0 and cur['di_diff'] > -25.0 and hour not in [15, 16, 18]:
                return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "reason": "v24 Unlocked RSI Low"}
        if sig == "SELL" and clean_reason == "RSI too high":
            if cur['vol_ratio'] > 1.25 and cur['atr_pct'] > 0.40 and hour not in [1, 6, 18]:
                return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "reason": "v24 Unlocked RSI High"}

        if step_mode == 2: return res

        # Step Mode 3: Step 2 + Unlock Remaining High-Probability Breakouts
        if sig == "BUY" and clean_reason in ["BUY Trend Exhaustion Block", "BUY Extreme Low Volume Breakout Block"]:
            if cur['vol_ratio'] > 1.0 and cur['rsi_7'] > 55.0 and cur['di_diff'] > 5.0:
                return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "reason": "v24 Unlocked Momentum"}
        if sig == "SELL" and clean_reason in ["SELL Low Volatility Upper BB Block", "SELL Momentum Conflict Block", "SELL Low ADX Above EMA50 Block"]:
            if cur['vol_ratio'] > 1.30 and cur['rsi'] > 55.0 and cur['body_pct'] > 0.50:
                return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "reason": "v24 Unlocked SELL Breakout"}

        return res

    for mode in [0, 1, 2, 3]:
        wins, losses, be, trades, pnl = 0, 0, 0, 0, 0.0
        sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
        unlocked_wins = 0; unlocked_losses = 0
        
        for i in range(100, len(rates) - 10):
            res = eval_candidate(df_master, i, step_mode=mode)
            if res and res.get("signal") in ["BUY", "SELL"]:
                sig = res["signal"]; entry = res["entry"]; sl = res["sl"]; tp = res["tp"]
                reason = res.get("reason", "")
                is_unlocked = "v24 Unlocked" in reason
                
                # Deduplication
                if sig == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
                if sig == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
                
                future_rates = rates[i+1:]
                be_trig = entry + ((tp - entry) * 0.4) if sig == "BUY" else entry - ((entry - tp) * 0.4)
                be_act = False
                for f_bar in future_rates:
                    if sig == "BUY":
                        if f_bar['low'] <= sl:
                            if be_act: be += 1
                            else:
                                losses += 1; pnl -= ((entry - sl) * 10 * compound); sl_buy_count += 1; last_buy_loss = entry
                                if is_unlocked: unlocked_losses += 1
                            trades += 1; break
                        elif f_bar['high'] >= tp:
                            wins += 1; trades += 1; sl_buy_count = 0; pnl += ((tp - entry) * 10 * compound)
                            if is_unlocked: unlocked_wins += 1
                            break
                        if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                    elif sig == "SELL":
                        if f_bar['high'] >= sl:
                            if be_act: be += 1
                            else:
                                losses += 1; pnl -= ((sl - entry) * 10 * compound); sl_sell_count += 1; last_sell_loss = entry
                                if is_unlocked: unlocked_losses += 1
                            trades += 1; break
                        elif f_bar['low'] <= tp:
                            wins += 1; trades += 1; sl_sell_count = 0; pnl += ((entry - tp) * 10 * compound)
                            if is_unlocked: unlocked_wins += 1
                            break
                        if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry

        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        print(f"Step Mode {mode} | Wins: {wins:3d} (Unl: +{unlocked_wins:2d}) | Losses: {losses:2d} (Unl: +{unlocked_losses:2d}) | BE: {be:2d} | WR: {win_rate:6.2f}% | PnL: ${pnl:11,.2f}")

    mt5.shutdown()

if __name__ == "__main__":
    optimize_200k()
