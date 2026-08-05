import MetaTrader5 as mt5
import pandas as pd
import argparse
from datetime import datetime, timedelta
import sys
import os

# Add parent directories to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import config
from strategy20_14 import strategy_20_14

def run_backtest(days, tf_list, compound):
    mt5.initialize()
    symbol = "XAUUSD.iux"
    
    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "H12": mt5.TIMEFRAME_H12, "D1": mt5.TIMEFRAME_D1
    }
    
    if tf_list == ["all"]:
        tf_list = ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1"]
        
    print(f"\n--- Backtest S20.14 Full Trading ---")
    print(f"Days: {days}, Compound: {compound}")
    print(f"{'Timeframe':<10} | {'Trades':<8} | {'Win':<6} | {'Loss':<6} | {'Win Rate %':<12} | {'Net P&L ($)':<12}")
    print("-" * 65)
    
    total_trades = 0
    total_win = 0
    total_loss = 0
    total_pnl = 0.0
    global_pattern_counts = {}
    utc_from = datetime.now()
    utc_to = utc_from - timedelta(days=days)
    
    for tf_str in tf_list:
        tf = tf_map.get(tf_str)
        if not tf: continue
        
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, days * 24 * 60 // (int(tf_str[1:]) if tf_str[1:].isdigit() else 60))
        if rates is None or len(rates) == 0:
            print(f"{tf_str:<10} | No Data")
            continue
            
        trades = 0
        win = 0
        loss = 0
        pnl = 0.0
        balance = 10000.0
        tf_pattern_counts = {}
        for i in range(30, len(rates) - 1):
            subset = rates[i-30:i+1]
            res = strategy_20_14(subset, tf_str)
            if res['signal'] in ['BUY', 'SELL']:
                trades += 1
                pat = res.get('pattern', 'Unknown')
                tf_pattern_counts[pat] = tf_pattern_counts.get(pat, 0) + 1
                global_pattern_counts[pat] = global_pattern_counts.get(pat, 0) + 1
                entry = res['entry']
                sl = res['sl']
                tp = res['tp']
                
                # Check outcome on the next bar
                next_bar = rates[i+1]
                
                if res['signal'] == 'BUY':
                    if next_bar['low'] <= sl:
                        loss += 1
                        loss_amt = 50 * compound
                        pnl -= loss_amt
                        balance -= loss_amt
                    elif next_bar['high'] >= tp:
                        win += 1
                        win_amt = 100 * compound
                        pnl += win_amt
                        balance += win_amt
                elif res['signal'] == 'SELL':
                    if next_bar['high'] >= sl:
                        loss += 1
                        loss_amt = 50 * compound
                        pnl -= loss_amt
                        balance -= loss_amt
                    elif next_bar['low'] <= tp:
                        win += 1
                        win_amt = 100 * compound
                        pnl += win_amt
                        balance += win_amt
                        
        win_rate = (win / trades * 100) if trades > 0 else 0
        total_trades += trades
        total_win += win
        total_loss += loss
        total_pnl += pnl
        
        pattern_str = " | ".join([f"{k}: {v}" for k, v in tf_pattern_counts.items()])
        print(f"{tf_str:<10} | {trades:<8} | {win:<6} | {loss:<6} | {win_rate:<12.2f} | {pnl:,.2f} | {pattern_str}")
        
    total_win_rate = (total_win / total_trades * 100) if total_trades > 0 else 0
    print("-" * 65)
    total_pattern_str = " | ".join([f"{k}: {v}" for k, v in global_pattern_counts.items()])
    print(f"{'Total':<10} | {total_trades:<8} | {total_win:<6} | {total_loss:<6} | {total_win_rate:<12.2f} | {total_pnl:,.2f} | {total_pattern_str}")
    
    mt5.shutdown()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--tf", nargs="+", default=["all"])
    parser.add_argument("--compound", type=float, default=1.0)
    args = parser.parse_args()
    
    run_backtest(args.days, args.tf, args.compound)
