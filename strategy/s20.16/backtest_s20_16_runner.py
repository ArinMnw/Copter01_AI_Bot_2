import argparse
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import strategy20_16
import config

def run_backtest(days=365, tf_list=["H1"], compound=1.0, symbol="XAUUSD.iux"):
    path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
    # Try to initialize with path, if fails try without path
    if not mt5.initialize(path=path): 
        if not mt5.initialize():
            print("MT5 initialize failed")
            return
        
    print(f"Running S20.16 backtest for {days} days, TFs: {tf_list}, Compound: {compound}")
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "H12": mt5.TIMEFRAME_H12, "D1": mt5.TIMEFRAME_D1
    }
    
    results = []
    
    for tf_name in tf_list:
        print(f"\n--- Processing TF: {tf_name} ---")
        if tf_name not in tf_map:
            print(f"Invalid TF: {tf_name}")
            continue
            
        current_days = days
        rates = None
        while current_days > 0:
            st = end_time - timedelta(days=current_days)
            rates = mt5.copy_rates_range(symbol, tf_map[tf_name], st, end_time)
            if rates is not None and len(rates) > 0:
                break
            current_days -= 30

        if rates is None or len(rates) == 0:
            print("No data received")
            continue
        print(f"Loaded {len(rates)} bars for {tf_name} ({current_days} days)")
            
        df_master = strategy20_16.compute_indicators_df(rates)
        
        for tpsl_mode in ["S20.13.23", "S20.14.23"]:
            config.S20_16_TPSL_MODE = tpsl_mode
            print(f"   Mode: {tpsl_mode} ... ", end="", flush=True)
            
            wins = 0; losses = 0; be = 0; trades = 0; pnl = 0.0
            max_pnl = 0.0; max_dd = 0.0
            
            for i in range(100, len(rates) - 10):
                res = strategy20_16.evaluate_bar(df_master, i, tf=tf_name)
                if not res or res.get("signal") not in ["BUY", "SELL"]: continue
                
                sig = res.get("signal")
                entry = res.get("entry")
                sl = res.get("sl")
                tp = res.get("tp")
                
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
                elif closed_type == "LOSS":
                    losses += 1; trades += 1; pnl -= ((entry - sl) * 10 * compound) if sig == "BUY" else ((sl - entry) * 10 * compound)
                elif closed_type == "BE":
                    be += 1

                if pnl > max_pnl: max_pnl = pnl
                dd = max_pnl - pnl
                if dd > max_dd: max_dd = dd

            wr_wl = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
            print(f"Done! WR: {wr_wl:.2f}% | Net: ${pnl:,.2f}")
            results.append({
                "TF": tf_name,
                "TPSL_MODE": tpsl_mode,
                "Trades": trades,
                "Wins": wins,
                "Losses": losses,
                "BE": be,
                "WinRate(%)": round(wr_wl, 2),
                "NetProfit($)": round(pnl, 2),
                "MaxDD($)": round(max_dd, 2)
            })

    mt5.shutdown()
    
    if results:
        df_res = pd.DataFrame(results)
        csv_path = os.path.join(os.path.dirname(__file__), "S20_16_backtest_summary.csv")
        df_res.to_csv(csv_path, index=False)
        print(f"\n✅ Saved detailed report to: {csv_path}")
        print("\n=== SUMMARY TABLE ===")
        print(df_res.to_string(index=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Backtest Runner for S20.16')
    parser.add_argument('--days', type=int, default=365, help='Number of days to backtest')
    parser.add_argument('--tf', type=str, default='M1,M5,M15,M30,H1,H4,D1', help='Timeframes to backtest (comma separated)')
    parser.add_argument('--compound', type=float, default=1.0, help='Compound multiplier (e.g. 1.0, 1.5)')
    
    args = parser.parse_args()
    tf_list = args.tf.split(",") if args.tf else ["M1","M5","M15","M30","H1","H4","D1"]
    
    run_backtest(days=args.days, tf_list=tf_list, compound=args.compound)
