import argparse
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from config import SYMBOL
from strategy20_13_7 import strategy_20_13_7

def run_backtest(days, tf_list, compound, symbol="XAUUSD.iux"):
    if not mt5.initialize():
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
            
            tf_mt5 = mt5_tfs[tf_name]
            now = datetime.now()
            start = now - timedelta(days=period)
            
            rates = mt5.copy_rates_range(symbol, tf_mt5, start, now)
            if rates is None or len(rates) == 0:
                print(f"| **{tf_name}** | 0 | 0 | 0 | 0% | N/A | $0.00 |")
                continue
                
            trades = 0
            wins = 0
            losses = 0
            be = 0
            pnl = 0.0
            
            balance = 1000.0
            
            sl_buy_count = 0
            sl_sell_count = 0
            last_buy_loss_entry = 0.0
            last_sell_loss_entry = 0.0
            
            for i in range(100, len(rates) - 1):
                slice_rates = rates[:i]
                res = strategy_20_13_7(slice_rates, tf=tf_name)
                if res.get("signal") in ["BUY", "SELL"]:
                    signal = res["signal"]
                    entry = res["entry"]
                    sl = res["sl"]
                    tp = res["tp"]
                    
                    df_slice = pd.DataFrame(slice_rates)
                    cur_atr = df_slice['high'].sub(df_slice['low']).rolling(14).mean().iloc[-1]
                    
                    if signal == "BUY" and sl_buy_count >= 2:
                        if abs(entry - last_buy_loss_entry) > (cur_atr * 2.5):
                            sl_buy_count = 0
                        else:
                            continue
                            
                    if signal == "SELL" and sl_sell_count >= 2:
                        if abs(entry - last_sell_loss_entry) > (cur_atr * 2.5):
                            sl_sell_count = 0
                        else:
                            continue
                    
                    rr_ratio = round(abs(tp - entry) / abs(entry - sl), 2) if abs(entry - sl) > 0 else 0.0
                    
                    df_slice = pd.DataFrame(slice_rates)
                    delta = df_slice['close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rs = gain / loss
                    cur_rsi = (100 - (100 / (1 + rs))).iloc[-1]
                    ema_50 = df_slice['close'].ewm(span=50, adjust=False).mean().iloc[-1]
                    ema_200 = df_slice['close'].ewm(span=200, adjust=False).mean().iloc[-1]
                    close_px = df_slice['close'].iloc[-1]
                    cur_trend = "UP" if close_px > ema_50 and ema_50 > ema_200 else ("DN" if close_px < ema_50 and ema_50 < ema_200 else "SIDE")
                    dist_ema50 = round(((close_px - ema_50) / close_px) * 100, 3)
                    dist_ema200 = round(((close_px - ema_200) / close_px) * 100, 3)
                    cur_atr = df_slice['high'].sub(df_slice['low']).rolling(14).mean().iloc[-1]
                    
                    dt_str = datetime.fromtimestamp(rates[i-1]['time']).strftime("%Y-%m-%d %H:%M")
                    
                    closed = False
                    be_active = False
                    
                    tp_dist = abs(tp - entry)
                    sd15_dist = tp_dist * (1.5 / 2.6)
                    if signal == "BUY":
                        be_trigger = entry + sd15_dist
                    else:
                        be_trigger = entry - sd15_dist
                    
                    for j in range(i, len(rates)):
                        future_low = rates[j]['low']
                        future_high = rates[j]['high']
                        
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
            target_dates = ["2026-07-16 23:00", "2026-07-17 21:00", "2026-07-17 23:00"]
            found_targets = []
            for dt in target_dates:
                matches = df_trades[(df_trades['Time (BKK)'].str.contains(dt)) & (df_trades['Type'] == 'BUY')]
                if not matches.empty:
                    found_targets.append(dt)
                    
            print(f"\n--- SNIPER RULE CHECK ---")
            for dt in target_dates:
                status = "✅ FOUND" if dt in found_targets else "❌ MISSING"
                print(f"{dt}: {status}")
            
            if len(found_targets) == len(target_dates):
                print("🎯 SNIPER RULE PASSED!")
            else:
                print("⚠️ SNIPER RULE FAILED!")
        
    mt5.shutdown()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=150)
    parser.add_argument("--tf", type=str, default="H1")
    parser.add_argument("--compound", type=float, default=1.0)
    args = parser.parse_args()
    
    if args.tf == "all":
        tf_list = ["all"]
    else:
        tf_list = [t.strip() for t in args.tf.split(",")]
    
    run_backtest(args.days, tf_list, args.compound)
