import argparse
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import strategy20_13_24
import config

def run_official_verify(days=700, tf_list=["H1"], compound=1.5, symbol="XAUUSD.iux"):
    path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
    if not mt5.initialize(path=path): 
        print("MT5 initialize failed")
        return
        
    print(f"Running backtest for {days} days, TFs: {tf_list}, Compound: {compound}")
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    # We only test H1 in this specific script as per the V24 requirements, but we loop over the tf_list just in case
    for tf_name in tf_list:
        print(f"\n--- Processing TF: {tf_name} ---")
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1 if tf_name == "H1" else mt5.TIMEFRAME_H1, start_time, end_time)
        if rates is None or len(rates) == 0:
            print("No data received")
            continue
            
        df_master = strategy20_13_24.compute_indicators_df(rates)
        
        wins = 0; losses = 0; be = 0; trades = 0; pnl = 0.0
        sl_buy_count = 0; sl_sell_count = 0; last_buy_loss = -99999.0; last_sell_loss = -99999.0
        master_dates = {"2026-07-16 16:00": False, "2026-07-17 14:00": False, "2026-07-17 16:00": False}

        for i in range(100, len(rates) - 10):
            res = strategy20_13_24.evaluate_bar(df_master, i, tf=tf_name)
            if not res or res.get("signal") not in ["BUY", "SELL"]: continue
            
            sig = res.get("signal")
            entry = res.get("entry")
            sl = res.get("sl")
            tp = res.get("tp")
            
            # SL Deduplication protection
            if sig == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
            if sig == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
            
            t_str = df_master.iloc[i]['time_dt'].strftime("%Y-%m-%d %H:%M")
            if t_str in master_dates: master_dates[t_str] = True
            
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
                    
            if closed_type == "WIN":
                wins += 1; trades += 1; pnl += ((tp - entry) * 10 * compound) if sig == "BUY" else ((entry - tp) * 10 * compound)
                if sig == "BUY": sl_buy_count = 0
                else: sl_sell_count = 0
            elif closed_type == "LOSS":
                losses += 1; trades += 1; pnl -= ((entry - sl) * 10 * compound) if sig == "BUY" else ((sl - entry) * 10 * compound)
                if sig == "BUY": sl_buy_count += 1; last_buy_loss = entry
                else: sl_sell_count += 1; last_sell_loss = entry
            elif closed_type == "BE":
                be += 1

        wr_wl = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
        print("=========================================================")
        print(f"OFFICIAL STRATEGY S20.13.24 VALIDATION ({days} DAYS):")
        print(f"Wins: {wins} | Losses: {losses} | BE: {be} | Total: {trades}")
        print(f"Win Rate (W/L): {wr_wl:.2f}%")
        print(f"Net Profit: ${pnl:,.2f}")
        print(f"Master Dates Found (UTC): {master_dates}")
        print(f"All Master Dates Valid: {all(master_dates.values())}")
        print("=========================================================")

    mt5.shutdown()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Backtest Runner for S20.13.24')
    parser.add_argument('--days', type=int, default=700, help='Number of days to backtest')
    parser.add_argument('--tf', type=str, default='H1', help='Timeframes to backtest (comma separated)')
    parser.add_argument('--compound', type=float, default=1.5, help='Compound multiplier (e.g. 1.5, 2.0)')
    
    args = parser.parse_args()
    
    tf_list = args.tf.split(",") if args.tf else ["H1"]
    
    run_official_verify(days=args.days, tf_list=tf_list, compound=args.compound)
