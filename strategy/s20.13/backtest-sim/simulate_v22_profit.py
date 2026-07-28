import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from strategy20_13_21 import compute_indicators_df, evaluate_bar

def sim_v22(days=365, symbol="XAUUSD.iux", compound=1.5):
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

    wins22, losses22, be22, trades22, pnl22 = 0, 0, 0, 0, 0.0
    sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
    
    all_trades_log = []
    
    for i in range(100, len(rates) - 10):
        res = evaluate_bar(df_master, i, tf="H1")
        if res and res.get("signal") in ["BUY", "SELL"]:
            signal = res["signal"]; entry = res["entry"]; sl = res["sl"]; tp = res["tp"]
            cur = df_master.iloc[i]
            
            # v22 Precision Filters
            if signal == "SELL":
                if cur['dist_ema50'] < 10.0 and cur['dist_ema200'] > 50.0: continue
                if cur['rsi'] > 55.0 and cur['di_diff'] < -3.0: continue
                if cur['rsi'] > 58.0 and cur['di_diff'] > 10.0: continue
                if cur['rsi'] < 50.0 and cur['dist_ema200'] > 80.0: continue
                if cur['z_score'] < -1.50 and cur['upper_wick_pct'] > 0.30: continue
            elif signal == "BUY":
                if cur['rsi'] < 48.0 and cur['di_diff'] > 0.0: continue
                
            if signal == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
            if signal == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
            
            entry_time = datetime.fromtimestamp(rates[i]['time'])
            dt_str = entry_time.strftime('%Y-%m-%d %H:%M')
            
            future_rates = rates[i+1:]
            be_trig = entry + ((tp - entry) * 0.4) if signal == "BUY" else entry - ((entry - tp) * 0.4)
            be_act = False
            closed = False
            
            for f_bar in future_rates:
                if signal == "BUY":
                    if f_bar['low'] <= sl:
                        if be_act:
                            be22 += 1; all_trades_log.append({"time": dt_str, "type": signal, "pnl": 0.0, "reason": "BE"})
                        else:
                            losses22 += 1; pnl22 -= ((entry - sl) * 10 * compound)
                            sl_buy_count += 1; last_buy_loss = entry
                            all_trades_log.append({"time": dt_str, "type": signal, "pnl": -((entry - sl) * 10 * compound), "reason": "SL"})
                        trades22 += 1; closed = True; break
                    elif f_bar['high'] >= tp:
                        wins22 += 1; trades22 += 1; sl_buy_count = 0
                        pnl22 += ((tp - entry) * 10 * compound)
                        all_trades_log.append({"time": dt_str, "type": signal, "pnl": ((tp - entry) * 10 * compound), "reason": "TP"})
                        closed = True; break
                    if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                elif signal == "SELL":
                    if f_bar['high'] >= sl:
                        if be_act:
                            be22 += 1; all_trades_log.append({"time": dt_str, "type": signal, "pnl": 0.0, "reason": "BE"})
                        else:
                            losses22 += 1; pnl22 -= ((sl - entry) * 10 * compound)
                            sl_sell_count += 1; last_sell_loss = entry
                            all_trades_log.append({"time": dt_str, "type": signal, "pnl": -((sl - entry) * 10 * compound), "reason": "SL"})
                        trades22 += 1; closed = True; break
                    elif f_bar['low'] <= tp:
                        wins22 += 1; trades22 += 1; sl_sell_count = 0
                        pnl22 += ((entry - tp) * 10 * compound)
                        all_trades_log.append({"time": dt_str, "type": signal, "pnl": ((entry - tp) * 10 * compound), "reason": "TP"})
                        closed = True; break
                    if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry
                    
            if not closed:
                all_trades_log.append({"time": dt_str, "type": signal, "pnl": 0.0, "reason": "OPEN"})
                
    win_rate_all = (wins22 / trades22 * 100) if trades22 > 0 else 0
    win_rate_wl = (wins22 / (wins22 + losses22) * 100) if (wins22 + losses22) > 0 else 0
    
    print("\n================== S20.13.22 SIMULATION RESULTS (365 DAYS) ==================")
    print(f"Total Trades : {trades22}")
    print(f"Wins (TP)    : {wins22}")
    print(f"Losses (SL)  : {losses22}")
    print(f"Break Even   : {be22}")
    print(f"Win/Loss Rate: {win_rate_wl:.2f}% (Target: >90%)")
    print(f"All Trade WR : {win_rate_all:.2f}%")
    print(f"Net P&L ($)  : ${pnl22:,.2f} (Target: >$100k)")
    
    df_log = pd.DataFrame(all_trades_log)
    print(f"\n--- SNIPER RULE CHECK (Mid-July BUYs) ---")
    sniper_buys = df_log[(df_log['time'].str.contains('2026-07-16|2026-07-17')) & (df_log['type'] == 'BUY')]
    print(sniper_buys)
    if len(sniper_buys) >= 3:
        print("🎯 SNIPER RULE PASSED (All 3 Master BUY orders present!)")
    else:
        print("⚠️ SNIPER RULE WARNING: Found fewer than 3 orders in mid-July")
        
    mt5.shutdown()

if __name__ == "__main__":
    sim_v22()
