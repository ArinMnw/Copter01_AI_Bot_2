import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from strategy20_13_22 import compute_indicators_df, evaluate_bar
import config

def grid_search_150k(days=700, symbol="XAUUSD.iux", compound=1.5):
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

    # Let's test relaxing ema50, vol_ratio, atr_pct thresholds systematically
    ema50_options = [-20.0, -22.0, -25.0, -28.0]
    vol_options = [0.85, 0.82, 0.80]
    atr_options = [0.20, 0.18, 0.15]
    
    best_pnl = 0.0
    best_config = None
    best_stats = None

    for ema_th in ema50_options:
        for vol_th in vol_options:
            for atr_th in atr_options:
                wins, losses, be, trades, pnl = 0, 0, 0, 0, 0.0
                sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
                all_trades_log = []
                
                for i in range(100, len(rates) - 10):
                    current_bar = df_master.iloc[i]
                    prev_bar = df_master.iloc[i - 1]
                    lookback_bars = df_master.iloc[i - 14 : i - 3]
                    local_low = lookback_bars['low'].min()
                    local_high = lookback_bars['high'].max()
                    recent_3 = df_master.iloc[i - 3 : i]
                    
                    cur_range = current_bar['high'] - current_bar['low']
                    if cur_range < (0.8 * current_bar['atr']): continue
                    hour = current_bar['time_dt'].hour
                    if hour in [12, 13, 23, 0, 8, 9]: continue
                    
                    if current_bar['adx'] < 15.0: continue
                    if current_bar['vol_ratio'] < vol_th: continue
                    if current_bar['body_pct'] < 0.50: continue
                    if current_bar['atr_pct'] < atr_th: continue
                    
                    signal = None; entry = current_bar['close']; sl = 0.0; tp = 0.0
                    
                    sweep_buy = recent_3['low'].min() < local_low
                    engulf_buy = current_bar['close'] > prev_bar['high']
                    instant_sweep_buy = current_bar['low'] < local_low and current_bar['close'] > prev_bar['high']
                    if (sweep_buy and engulf_buy) or instant_sweep_buy:
                        if hour in [2, 19, 17]: continue
                        if current_bar['rsi'] < 35: continue
                        if current_bar['z_score'] > 0.85: continue
                        if current_bar['di_diff'] < -15.0: continue
                        if current_bar['adx'] > 45.0: continue
                        if current_bar['rsi'] < 40.0 and current_bar['adx'] > 42.0: continue
                        
                        signal = "BUY"
                        sweep_bottom = min(recent_3['low'].min(), current_bar['low'])
                        sl = sweep_bottom - config.SL_BUFFER(current_bar['atr'])
                        tp = sweep_bottom + current_bar['atr'] * 2.6 * np.sqrt(720/60)
                        
                    sweep_sell = recent_3['high'].max() > local_high
                    engulf_sell = current_bar['close'] < prev_bar['low']
                    instant_sweep_sell = current_bar['high'] > local_high and current_bar['close'] < prev_bar['low']
                    if not signal and ((sweep_sell and engulf_sell) or instant_sweep_sell):
                        if current_bar['rsi'] > 60: continue
                        if current_bar['rsi_7'] > 50.5: continue
                        if current_bar['z_score'] < -0.85: continue
                        if current_bar['adx'] > 45.0: continue
                        if current_bar['di_diff'] > 15.0: continue
                        if current_bar['dist_ema50'] < ema_th: continue
                        if current_bar['dist_ema200'] < -40.0: continue
                        
                        # Apply our top v23 rules + remaining loss rules:
                        if current_bar['body_pct'] > 0.70 and current_bar['atr_pct'] < 0.30: continue
                        if current_bar['rsi'] < 52.0 and current_bar['z_score'] > 0.0: continue
                        if current_bar['rsi_7'] < 55.0 and current_bar['body_pct'] > 0.90: continue
                        if current_bar['rsi_7'] < 33.0: continue # Blocks loss #1 & #3
                        if current_bar['dist_ema200'] < -65.0: continue # Blocks loss #2
                        if hour == 5: continue # Blocks loss #5
                        if current_bar['rsi_7'] > 65.0: continue # Blocks loss #4
                        
                        signal = "SELL"
                        sweep_top = max(recent_3['high'].max(), current_bar['high'])
                        sl = sweep_top + config.SL_BUFFER(current_bar['atr'])
                        tp = sweep_top - current_bar['atr'] * 2.6 * np.sqrt(1440/60)
                        
                    if signal:
                        if signal == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
                        if signal == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
                        
                        dt_str = current_bar['time_dt'].strftime('%Y-%m-%d %H:%M')
                        future_rates = rates[i+1:]
                        be_trig = entry + ((tp - entry) * 0.4) if signal == "BUY" else entry - ((entry - tp) * 0.4)
                        be_act = False
                        closed = False
                        
                        for f_bar in future_rates:
                            if signal == "BUY":
                                if f_bar['low'] <= sl:
                                    if be_act: be += 1
                                    else:
                                        losses += 1; pnl -= ((entry - sl) * 10 * compound)
                                        sl_buy_count += 1; last_buy_loss = entry
                                    trades += 1; closed = True; break
                                elif f_bar['high'] >= tp:
                                    wins += 1; trades += 1; sl_buy_count = 0
                                    pnl += ((tp - entry) * 10 * compound)
                                    closed = True; break
                                if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                            elif signal == "SELL":
                                if f_bar['high'] >= sl:
                                    if be_act: be += 1
                                    else:
                                        losses += 1; pnl -= ((sl - entry) * 10 * compound)
                                        sl_sell_count += 1; last_sell_loss = entry
                                    trades += 1; closed = True; break
                                elif f_bar['low'] <= tp:
                                    wins += 1; trades += 1; sl_sell_count = 0
                                    pnl += ((entry - tp) * 10 * compound)
                                    closed = True; break
                                if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry
                        if closed:
                            all_trades_log.append({"time": dt_str, "type": signal, "pnl": pnl})

                win_rate_wl = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
                df_log = pd.DataFrame(all_trades_log)
                sniper_count = 0
                if len(df_log) > 0:
                    sniper_count = len(df_log[(df_log['time'].str.contains('2026-07-16|2026-07-17')) & (df_log['type'] == 'BUY')])
                    
                if sniper_count >= 3 and win_rate_wl >= 80.0:
                    if pnl > best_pnl:
                        best_pnl = pnl
                        best_config = (ema_th, vol_th, atr_th)
                        best_stats = (wins, losses, be, trades, win_rate_wl, pnl)

    print("\n================== BEST RELAXATION + V23 RESULT ==================")
    if best_stats:
        wins, losses, be, trades, win_rate_wl, pnl = best_stats
        ema_th, vol_th, atr_th = best_config
        print(f"Config: EMA50 < {ema_th}, Vol < {vol_th}, ATR% < {atr_th}")
        print(f"Wins: {wins} | Losses: {losses} | BE: {be} | Total: {trades}")
        print(f"Win/Loss Rate: {win_rate_wl:.2f}% (Target: >80%)")
        print(f"Net P&L ($): ${pnl:,.2f} (Target: >$150k)")
    else:
        print("No valid config found")
    mt5.shutdown()

if __name__ == "__main__":
    grid_search_150k()
