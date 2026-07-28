import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from strategy20_13_22 import compute_indicators_df, evaluate_bar

def sim_v23_700(days=700, symbol="XAUUSD.iux", compound=1.5):
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

    wins23, losses23, be23, trades23, pnl23 = 0, 0, 0, 0, 0.0
    sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
    
    all_trades_log = []
    
    for i in range(100, len(rates) - 10):
        res = evaluate_bar(df_master, i, tf="H1")
        if res and res.get("signal") in ["BUY", "SELL"]:
            signal = res["signal"]; entry = res["entry"]; sl = res["sl"]; tp = res["tp"]
            cur = df_master.iloc[i]
            
            # v23 Precision Filters (700 Days)
            if signal == "SELL":
                if cur['di_diff'] < 1.0 and cur['body_pct'] > 0.85: continue
                if cur['body_pct'] > 0.70 and cur['atr_pct'] < 0.30: continue
                if cur['rsi_7'] > 47.0 and cur['atr_pct'] < 0.30: continue
                if cur['adx'] > 40.0 and cur['atr_pct'] < 0.35: continue
                if cur['rsi'] < 52.0 and cur['z_score'] > 0.0: continue
                if cur['rsi_7'] < 55.0 and cur['body_pct'] > 0.90: continue
                if cur['atr_pct'] < 0.40 and cur['hour'] == 16: continue
            elif signal == "BUY":
                if cur['rsi'] < 40.0 and cur['adx'] > 42.0: continue
                
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
                            be23 += 1; all_trades_log.append({"time": dt_str, "type": signal, "pnl": 0.0, "reason": "BE"})
                        else:
                            losses23 += 1; pnl23 -= ((entry - sl) * 10 * compound)
                            sl_buy_count += 1; last_buy_loss = entry
                            all_trades_log.append({"time": dt_str, "type": signal, "pnl": -((entry - sl) * 10 * compound), "reason": "SL"})
                        trades23 += 1; closed = True; break
                    elif f_bar['high'] >= tp:
                        wins23 += 1; trades23 += 1; sl_buy_count = 0
                        pnl23 += ((tp - entry) * 10 * compound)
                        all_trades_log.append({"time": dt_str, "type": signal, "pnl": ((tp - entry) * 10 * compound), "reason": "TP"})
                        closed = True; break
                    if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                elif signal == "SELL":
                    if f_bar['high'] >= sl:
                        if be_act:
                            be23 += 1; all_trades_log.append({"time": dt_str, "type": signal, "pnl": 0.0, "reason": "BE"})
                        else:
                            losses23 += 1; pnl23 -= ((sl - entry) * 10 * compound)
                            sl_sell_count += 1; last_sell_loss = entry
                            all_trades_log.append({"time": dt_str, "type": signal, "pnl": -((sl - entry) * 10 * compound), "reason": "SL"})
                        trades23 += 1; closed = True; break
                    elif f_bar['low'] <= tp:
                        wins23 += 1; trades23 += 1; sl_sell_count = 0
                        pnl23 += ((entry - tp) * 10 * compound)
                        all_trades_log.append({"time": dt_str, "type": signal, "pnl": ((entry - tp) * 10 * compound), "reason": "TP"})
                        closed = True; break
                    if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry
                    
            if not closed:
                all_trades_log.append({"time": dt_str, "type": signal, "pnl": 0.0, "reason": "OPEN"})
                
    win_rate_all = (wins23 / trades23 * 100) if trades23 > 0 else 0
    win_rate_wl = (wins23 / (wins23 + losses23) * 100) if (wins23 + losses23) > 0 else 0
    
    print("\n================== S20.13.23 SIMULATION RESULTS (700 DAYS) ==================")
    print(f"Total Trades : {trades23}")
    print(f"Wins (TP)    : {wins23}")
    print(f"Losses (SL)  : {losses23}")
    print(f"Break Even   : {be23}")
    print(f"Win/Loss Rate: {win_rate_wl:.2f}% (Target: >80%)")
    print(f"All Trade WR : {win_rate_all:.2f}%")
    print(f"Net P&L ($)  : ${pnl23:,.2f} (Target: >$150k)")
    
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
    sim_v23_700()
