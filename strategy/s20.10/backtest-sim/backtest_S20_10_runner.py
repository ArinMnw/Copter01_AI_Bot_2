import MetaTrader5 as mt5
import argparse
import datetime
import pandas as pd
from typing import List, Dict

import sys
import os
# Add project root to sys.path so it can find config and mt5_utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
import config
import mt5_utils


import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from strategy20_10 import strategy_20_10

def run_backtest(days_list: List[int], tf_arg: str):
    print(f"Starting Backtest for S20.10...")
    print(f"Days: {days_list}, Timeframe: {tf_arg}")
    
    if not config.mt5_initialize(mt5):
        print("MT5 initialize failed")
        return

    symbol = config.SYMBOL
    if not mt5.symbol_select(symbol, True):
        print(f"Failed to select {symbol}")
        return
        
    tfs_to_test = []
    if tf_arg.lower() == 'all':
        tfs_to_test = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
    else:
        tfs_to_test = [tf_arg]
        
    for days in days_list:
        now_bkk = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=config.TZ_OFFSET)
        start_bkk = now_bkk - datetime.timedelta(days=days)
        
        # MT5 expects UTC+6 (which is BKK - 1h)
        start_mt5 = start_bkk - datetime.timedelta(hours=1)
        end_mt5 = now_bkk - datetime.timedelta(hours=1)
        
        results_summary = []
        print(f"\n[{days} Days Backtest Results]")
        
        for tf_name in tfs_to_test:
            mt5_tf = getattr(mt5, f"TIMEFRAME_{tf_name}")
            
            rates = mt5.copy_rates_range(symbol, mt5_tf, start_mt5, end_mt5)
            if rates is None or len(rates) == 0:
                results_summary.append({
                    "tf": tf_name, "trades": 0, "win": 0, "loss": 0,
                    "win_rate": 0, "freq_level": "-", "net_pl": 0.0
                })
                continue
                
            win_count = 0
            loss_count = 0
            net_pl = 0.0
            patterns_freq = {}
            
            # Simulate bar by bar
            window_size = 20
            contract_size = 100.0  # Gold standard contract size
            fixed_lot = 0.1
            spread = 2.0  # Assumed spread in pips
            commission = 7.0 * fixed_lot # Assumed $7 per lot
            
            for i in range(window_size, len(rates) - 1):
                window_rates = rates[i-window_size : i+1]
                
                # Enable the strategy config explicitly for the backtest
                config.S20_10_ENABLED = True
                res = strategy_20_10(window_rates, tf_name=tf_name, config=config)
                
                if res.get("signal") in ("BUY", "SELL"):
                    pat = res.get("pattern", "Unknown")
                    patterns_freq[pat] = patterns_freq.get(pat, 0) + 1
                    
                    # Check outcome using future bars to properly simulate LIMIT orders
                    entry_price = res["entry"]
                    sl = res["sl"]
                    tp = res["tp"]
                    is_buy = res["signal"] == "BUY"
                    
                    filled = False
                    closed = False
                    
                    # Iterate through future bars to simulate fill and close
                    for j in range(i+1, len(rates)):
                        future_bar = rates[j]
                        
                        # 1. Check if order gets filled or cancelled
                        if not filled:
                            if is_buy:
                                if future_bar['high'] >= tp:
                                    # Price reached target without filling us - Cancel order
                                    break
                                elif future_bar['low'] <= entry_price:
                                    filled = True
                            else:
                                if future_bar['low'] <= tp:
                                    # Price reached target without filling us - Cancel order
                                    break
                                elif future_bar['high'] >= entry_price:
                                    filled = True
                                
                        # 2. Check for SL / TP if filled
                        if filled:
                            if is_buy:
                                if future_bar['low'] <= sl:
                                    loss_count += 1
                                    loss_pts = entry_price - sl
                                    net_pl -= (loss_pts * contract_size * fixed_lot) + commission
                                    closed = True
                                    break
                                elif future_bar['high'] >= tp:
                                    win_count += 1
                                    win_pts = tp - entry_price - (spread * 0.1)
                                    net_pl += (win_pts * contract_size * fixed_lot) - commission
                                    closed = True
                                    break
                            else:
                                if future_bar['high'] >= sl:
                                    loss_count += 1
                                    loss_pts = sl - entry_price
                                    net_pl -= (loss_pts * contract_size * fixed_lot) + commission
                                    closed = True
                                    break
                                elif future_bar['low'] <= tp:
                                    win_count += 1
                                    win_pts = entry_price - tp - (spread * 0.1)
                                    net_pl += (win_pts * contract_size * fixed_lot) - commission
                                    closed = True
                                    break
            total_trades = win_count + loss_count
            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
            freq_level = max(patterns_freq, key=patterns_freq.get) if patterns_freq else "-"
            
            results_summary.append({
                "tf": tf_name,
                "trades": total_trades,
                "win": win_count,
                "loss": loss_count,
                "win_rate": win_rate,
                "freq_level": freq_level,
                "net_pl": net_pl
            })
            
        print("\n" + "="*90)
        print(f"| {'Timeframe':<10} | {'Trades':<8} | {'Win':<5} | {'Loss':<5} | {'Win Rate %':<12} | {'Most Freq Pattern':<20} | {'Net P&L ($)':<12} |")
        print("-" * 90)
        
        total_trades = sum(r["trades"] for r in results_summary)
        total_win = sum(r["win"] for r in results_summary)
        total_loss = sum(r["loss"] for r in results_summary)
        total_pl = sum(r["net_pl"] for r in results_summary)
        total_wr = (total_win / total_trades * 100) if total_trades > 0 else 0
        
        for r in results_summary:
            print(f"| {r['tf']:<10} | {r['trades']:<8} | {r['win']:<5} | {r['loss']:<5} | {r['win_rate']:<12.2f} | {r['freq_level']:<20} | {r['net_pl']:<12,.2f} |")
            
        print("-" * 90)
        print(f"| {'Total':<10} | {total_trades:<8} | {total_win:<5} | {total_loss:<5} | {total_wr:<12.2f} | {'-':<20} | {total_pl:<12,.2f} |")
        print("=" * 90)
        
    mt5.shutdown()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest S20.10 Strategy")
    parser.add_argument("--days", type=int, default=30, help="Number of days to backtest (or use 0 to run 30,60,90,120,180)")
    parser.add_argument("--tf", type=str, default="all", help="Timeframe to test (e.g. M1, M5, all)")
    args = parser.parse_args()
    
    days_list = [30, 60, 90, 120, 180] if args.days == 0 else [args.days]
    run_backtest(days_list, args.tf)
