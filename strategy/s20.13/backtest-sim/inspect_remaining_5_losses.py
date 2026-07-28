import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from strategy20_13_22 import compute_indicators_df, evaluate_bar

def inspect_5(days=700, symbol="XAUUSD.iux", compound=1.5):
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

    sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
    
    losses_list = []
    wins_list = []
    
    for i in range(100, len(rates) - 10):
        res = evaluate_bar(df_master, i, tf="H1")
        if res and res.get("signal") in ["BUY", "SELL"]:
            signal = res["signal"]; entry = res["entry"]; sl = res["sl"]; tp = res["tp"]
            cur = df_master.iloc[i]
            
            # The 3 SELL rules from test_combos:
            if signal == "SELL":
                if cur['body_pct'] > 0.70 and cur['atr_pct'] < 0.30: continue
                if cur['rsi'] < 52.0 and cur['z_score'] > 0.0: continue
                if cur['rsi_7'] < 55.0 and cur['body_pct'] > 0.90: continue
            elif signal == "BUY":
                if cur['rsi'] < 40.0 and cur['adx'] > 42.0: continue
                
            if signal == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
            if signal == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
            
            dt_str = datetime.fromtimestamp(rates[i]['time']).strftime('%Y-%m-%d %H:%M')
            future_rates = rates[i+1:]
            be_trig = entry + ((tp - entry) * 0.4) if signal == "BUY" else entry - ((entry - tp) * 0.4)
            be_act = False
            outcome = "OPEN"
            
            for f_bar in future_rates:
                if signal == "BUY":
                    if f_bar['low'] <= sl:
                        if be_act: outcome = "BE"
                        else:
                            outcome = "LOSS"
                            sl_buy_count += 1; last_buy_loss = entry
                            losses_list.append((dt_str, signal, cur))
                        break
                    elif f_bar['high'] >= tp:
                        outcome = "WIN"; sl_buy_count = 0; wins_list.append((dt_str, signal, cur)); break
                    if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                elif signal == "SELL":
                    if f_bar['high'] >= sl:
                        if be_act: outcome = "BE"
                        else:
                            outcome = "LOSS"
                            sl_sell_count += 1; last_sell_loss = entry
                            losses_list.append((dt_str, signal, cur))
                        break
                    elif f_bar['low'] <= tp:
                        outcome = "WIN"; sl_sell_count = 0; wins_list.append((dt_str, signal, cur)); break
                    if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry

    print(f"Total Wins: {len(wins_list)} | Total Losses: {len(losses_list)}")
    print("\n--- THE REMAINING LOSSES ---")
    for dt, sig, cur in losses_list:
        print(f"{dt} | {sig} | RSI:{cur['rsi']:.2f} RSI7:{cur['rsi_7']:.2f} ADX:{cur['adx']:.2f} DI_df:{cur['di_diff']:.2f} VolR:{cur['vol_ratio']:.2f} Z:{cur['z_score']:.2f} Body%:{cur['body_pct']:.2f} ATR%:{cur['atr_pct']:.2f} dEMA50:{cur['dist_ema50']:.2f} dEMA200:{cur['dist_ema200']:.2f} Hr:{cur['hour']}")

    mt5.shutdown()

if __name__ == "__main__":
    inspect_5()
