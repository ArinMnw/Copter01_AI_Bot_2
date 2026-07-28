import argparse
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from strategy20_13_22 import compute_indicators_df, evaluate_bar

def run_backtest(days, tf_list, compound, symbol="XAUUSD.iux"):
    path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
    if not mt5.initialize(path=path):
        print("MT5 initialize failed")
        return
        
    mt5_tfs = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "H12": mt5.TIMEFRAME_H12,
        "D1": mt5.TIMEFRAME_D1,
    }
    
    if tf_list == ["all"]:
        tf_list = list(mt5_tfs.keys())
        
    print(f"Running backtest for {days} days, TFs: {tf_list}, Compound: {compound}")
    
    periods = [30, 60, 90, 120, 180] if days == 0 else [days]
    
    for period in periods:
        print(f"\n--- Period: {period} Days ---")
        print("| Timeframe | Trades | Win | Loss | Win Rate % | Most Common Signal | Net P&L ($) |")
        print("|---|---|---|---|---|---|---|")
        
        total_trades = 0
        total_wins = 0
        total_losses = 0
        total_be = 0
        total_pnl = 0.0
        all_trades_log = []
        
        for tf_name in tf_list:
            if tf_name not in mt5_tfs:
                continue
            tf_code = mt5_tfs[tf_name]
            
            end_time = datetime.now()
            start_time = end_time - timedelta(days=period)
            
            rates = mt5.copy_rates_range(symbol, tf_code, start_time, end_time)
            if rates is None or len(rates) == 0:
                print(f"No rates for {symbol} on {tf_name}")
                continue
                
            trades = 0
            wins = 0
            losses = 0
            be = 0
            pnl = 0.0
            balance = 10000.0
            
            sl_buy_count = 0
            last_buy_loss_entry = 0.0
            sl_sell_count = 0
            last_sell_loss_entry = 0.0
            
            # Pre-compute indicators for all bars at once
            df_master = compute_indicators_df(rates)
            
            for i in range(100, len(rates) - 10):
                res = evaluate_bar(df_master, i, tf=tf_name)
                
                if res and res.get("signal") in ["BUY", "SELL"]:
                    signal = res["signal"]
                    entry = res["entry"]
                    sl = res["sl"]
                    tp = res["tp"]
                    
                    if signal == "BUY":
                        if sl_buy_count >= 1 and abs(entry - last_buy_loss_entry) <= 5.0:
                            continue
                    elif signal == "SELL":
                        if sl_sell_count >= 1 and abs(entry - last_sell_loss_entry) <= 5.0:
                            continue
                            
                    entry_time = datetime.fromtimestamp(rates[i]['time'])
                    dt_str = entry_time.strftime('%Y-%m-%d %H:%M')
                    
                    future_rates = rates[i+1:]
                    be_trigger = entry + ((tp - entry) * 0.4) if signal == "BUY" else entry - ((entry - tp) * 0.4)
                    be_active = False
                    closed = False
                    
                    for f_bar in future_rates:
                        future_high = f_bar['high']
                        future_low = f_bar['low']
                        
                        if signal == "BUY":
                            if future_low <= sl:
                                if be_active:
                                    be += 1
                                    all_trades_log.append({
                                        "Time (BKK)": dt_str,
                                        "Type": signal,
                                        "P&L": 0.0,
                                        "Reason": "BE"
                                    })
                                else:
                                    losses += 1
                                    loss_amt = -((entry - sl) * 10 * compound)
                                    pnl += loss_amt
                                    balance += loss_amt
                                    sl_buy_count += 1
                                    last_buy_loss_entry = entry
                                    all_trades_log.append({
                                        "Time (BKK)": dt_str,
                                        "Type": signal,
                                        "P&L": loss_amt,
                                        "Reason": "SL"
                                    })
                                trades += 1
                                closed = True
                                break
                            elif future_high >= tp:
                                wins += 1
                                trades += 1
                                sl_buy_count = 0
                                win_amt = ((tp - entry) * 10 * compound)
                                pnl += win_amt
                                balance += win_amt
                                all_trades_log.append({
                                    "Time (BKK)": dt_str,
                                    "Type": signal,
                                    "P&L": win_amt,
                                    "Reason": "TP"
                                })
                                closed = True
                                break
                            
                            if not be_active and future_high >= be_trigger:
                                be_active = True
                                sl = entry
                                
                        elif signal == "SELL":
                            if future_high >= sl:
                                if be_active:
                                    be += 1
                                    all_trades_log.append({
                                        "Time (BKK)": dt_str,
                                        "Type": signal,
                                        "P&L": 0.0,
                                        "Reason": "BE"
                                    })
                                else:
                                    losses += 1
                                    loss_amt = -((sl - entry) * 10 * compound)
                                    pnl += loss_amt
                                    balance += loss_amt
                                    sl_sell_count += 1
                                    last_sell_loss_entry = entry
                                    all_trades_log.append({
                                        "Time (BKK)": dt_str,
                                        "Type": signal,
                                        "P&L": loss_amt,
                                        "Reason": "SL"
                                    })
                                trades += 1
                                closed = True
                                break
                            elif future_low <= tp:
                                wins += 1
                                trades += 1
                                sl_sell_count = 0
                                win_amt = ((entry - tp) * 10 * compound)
                                pnl += win_amt
                                balance += win_amt
                                all_trades_log.append({
                                    "Time (BKK)": dt_str,
                                    "Type": signal,
                                    "P&L": win_amt,
                                    "Reason": "TP"
                                })
                                closed = True
                                break
                                
                            if not be_active and future_low <= be_trigger:
                                be_active = True
                                sl = entry
                                
                    if not closed:
                        all_trades_log.append({
                            "Time (BKK)": dt_str,
                            "Type": signal,
                            "P&L": 0.0,
                            "Reason": "OPEN"
                        })
                            
            win_rate = (wins / trades * 100) if trades > 0 else 0
            pnl_str = f"${pnl:,.2f}"
            print(f"| **{tf_name}** | {trades} | {wins} | {losses} | {win_rate:.2f}% | BE: {be} | {pnl_str} |")
            
            total_trades += trades
            total_wins += wins
            total_losses += losses
            total_be += be
            total_pnl += pnl
            
        total_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        total_pnl_str = f"${total_pnl:,.2f}"
        print(f"| **สรุปรวมทุก TF** | {total_trades} | {total_wins} | {total_losses} | {total_win_rate:.2f}% | BE: {total_be} | {total_pnl_str} |")
        
        if all_trades_log:
            df_trades = pd.DataFrame(all_trades_log)
            print(f"\n--- SNIPER RULE CHECK (Mid-July BUYs) ---")
            sniper_buys = df_trades[(df_trades['Time (BKK)'].str.contains('2026-07-16|2026-07-17')) & (df_trades['Type'] == 'BUY')]
            print(sniper_buys)
            if len(sniper_buys) >= 3:
                print("🎯 SNIPER RULE PASSED!")
            else:
                print("⚠️ SNIPER RULE WARNING!")
                
            df_trades.to_csv('s20_13_22_trades.csv', index=False)
        
    mt5.shutdown()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--tf", type=str, default="H1")
    parser.add_argument("--compound", type=float, default=1.5)
    args = parser.parse_args()
    
    if args.tf == "all":
        tf_list = ["all"]
    else:
        tf_list = [t.strip() for t in args.tf.split(",")]
    
    run_backtest(args.days, tf_list, args.compound)
