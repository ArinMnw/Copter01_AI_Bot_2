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
from strategy20_13 import strategy_20_13

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
    
    # 5 test periods
    periods = [30, 60, 90, 120, 180] if days == 0 else [days]
    
    for period in periods:
        print(f"\n--- Period: {period} Days ---")
        print("| Timeframe | Trades | Win | Loss | Win Rate % | Most Common Signal | Net P&L ($) |")
        print("|---|---|---|---|---|---|---|")
        
        total_trades = 0
        total_wins = 0
        total_losses = 0
        total_pnl = 0.0
        all_trades_log = []
        
        for tf_name in tf_list:
            if tf_name not in mt5_tfs:
                continue
            
            tf_mt5 = mt5_tfs[tf_name]
            # Fetch data (simplified for this script, we need BKK time logic)
            # time calculation
            now = datetime.now()
            start = now - timedelta(days=period)
            
            # Since MT5 rates are in server time, this is an approximation for backtest runner
            rates = mt5.copy_rates_range(symbol, tf_mt5, start, now)
            if rates is None or len(rates) == 0:
                print(f"| **{tf_name}** | 0 | 0 | 0 | 0% | N/A | $0.00 |")
                continue
                
            print(f"DEBUG: {tf_name} has {len(rates)} bars")
            trades = 0
            wins = 0
            losses = 0
            pnl = 0.0
            
            # Simulation loop
            balance = 1000.0
            
            sl_buy_count = 0
            sl_sell_count = 0
            last_buy_loss_entry = 0.0
            last_sell_loss_entry = 0.0
            
            for i in range(100, len(rates) - 1):
                slice_rates = rates[:i]
                res = strategy_20_13(slice_rates, tf=tf_name)
                if res.get("signal") in ["BUY", "SELL"]:
                    signal = res["signal"]
                    entry = res["entry"]
                    sl = res["sl"]
                    tp = res["tp"]
                    
                    df_slice = pd.DataFrame(slice_rates)
                    cur_atr = df_slice['high'].sub(df_slice['low']).rolling(14).mean().iloc[-1]
                    
                    # --- SL GUARD SIMULATION ---
                    if signal == "BUY" and sl_buy_count >= 2:
                        if abs(entry - last_buy_loss_entry) > (cur_atr * 2.5):
                            sl_buy_count = 0
                        else:
                            continue # BLOCKED by SL Guard
                            
                    if signal == "SELL" and sl_sell_count >= 2:
                        if abs(entry - last_sell_loss_entry) > (cur_atr * 2.5):
                            sl_sell_count = 0
                        else:
                            continue # BLOCKED by SL Guard
                    # ---------------------------
                    
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
                    print(f"[{tf_name}] {dt_str} OPEN {signal} @ {entry:.2f} | TP: {tp:.2f} | SL: {sl:.2f} | RR: {rr_ratio}")
                    
                    closed = False
                    be_active = False
                    
                    # Calculate SD 1.5 trigger distance (Fuel was 2.6, so 1.5 is 1.5/2.6 of the TP distance from base)
                    # For simplicity, we just take 1.5/2.6 of the (TP - Entry) distance as the trigger.
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
                                    print(f"  -> {datetime.fromtimestamp(rates[j]['time']).strftime('%Y-%m-%d %H:%M')} CLOSED BREAKEVEN")
                                    all_trades_log.append({
                                        "Time (BKK)": dt_str,
                                        "Close Time": datetime.fromtimestamp(rates[j]['time']).strftime('%Y-%m-%d %H:%M'),
                                        "TF": tf_name,
                                        "Type": signal,
                                        "RSI": round(cur_rsi, 1) if not pd.isna(cur_rsi) else 0,
                                        "Trend": cur_trend,
                                        "Dist50": dist_ema50,
                                        "Dist200": dist_ema200,
                                        "ATR": round(cur_atr, 2),
                                        "R:R": rr_ratio,
                                        "Entry": entry,
                                        "SL": sl,
                                        "TP": tp,
                                        "Lot": compound,
                                        "P&L": 0.0,
                                        "Balance": balance,
                                        "Reason": "BE"
                                    })
                                else:
                                    losses += 1
                                    loss_amt = -((entry - sl) * 10 * compound)
                                    pnl += loss_amt
                                    balance += loss_amt
                                    sl_buy_count += 1
                                    last_buy_loss_entry = entry
                                    print(f"  -> {datetime.fromtimestamp(rates[j]['time']).strftime('%Y-%m-%d %H:%M')} CLOSED LOSS (Guard: {sl_buy_count})")
                                    all_trades_log.append({
                                        "Time (BKK)": dt_str,
                                        "Close Time": datetime.fromtimestamp(rates[j]['time']).strftime('%Y-%m-%d %H:%M'),
                                        "TF": tf_name,
                                        "Type": signal,
                                        "RSI": round(cur_rsi, 1) if not pd.isna(cur_rsi) else 0,
                                        "Trend": cur_trend,
                                        "Dist50": dist_ema50,
                                        "Dist200": dist_ema200,
                                        "ATR": round(cur_atr, 2),
                                        "R:R": rr_ratio,
                                        "Entry": entry,
                                        "SL": sl,
                                        "TP": tp,
                                        "Lot": compound,
                                        "P&L": loss_amt,
                                        "Balance": balance,
                                        "Reason": "SL"
                                    })
                                trades += 1
                                closed = True
                                break
                            elif future_high >= tp:
                                wins += 1
                                trades += 1
                                sl_buy_count = 0 # Reset guard on win
                                win_amt = ((tp - entry) * 10 * compound)
                                pnl += win_amt
                                balance += win_amt
                                print(f"  -> {datetime.fromtimestamp(rates[j]['time']).strftime('%Y-%m-%d %H:%M')} CLOSED WIN")
                                all_trades_log.append({
                                    "Time (BKK)": dt_str,
                                    "Close Time": datetime.fromtimestamp(rates[j]['time']).strftime('%Y-%m-%d %H:%M'),
                                    "TF": tf_name,
                                    "Type": signal,
                                    "RSI": round(cur_rsi, 1) if not pd.isna(cur_rsi) else 0,
                                    "Trend": cur_trend,
                                    "Dist50": dist_ema50,
                                    "Dist200": dist_ema200,
                                    "ATR": round(cur_atr, 2),
                                    "R:R": rr_ratio,
                                    "Entry": entry,
                                    "SL": sl,
                                    "TP": tp,
                                    "Lot": compound,
                                    "P&L": win_amt,
                                    "Balance": balance,
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
                                    print(f"  -> {datetime.fromtimestamp(rates[j]['time']).strftime('%Y-%m-%d %H:%M')} CLOSED BREAKEVEN")
                                    all_trades_log.append({
                                        "Time (BKK)": dt_str,
                                        "Close Time": datetime.fromtimestamp(rates[j]['time']).strftime('%Y-%m-%d %H:%M'),
                                        "TF": tf_name,
                                        "Type": signal,
                                        "RSI": round(cur_rsi, 1) if not pd.isna(cur_rsi) else 0,
                                        "Trend": cur_trend,
                                        "Dist50": dist_ema50,
                                        "Dist200": dist_ema200,
                                        "ATR": round(cur_atr, 2),
                                        "R:R": rr_ratio,
                                        "Entry": entry,
                                        "SL": sl,
                                        "TP": tp,
                                        "Lot": compound,
                                        "P&L": 0.0,
                                        "Balance": balance,
                                        "Reason": "BE"
                                    })
                                else:
                                    losses += 1
                                    loss_amt = -((sl - entry) * 10 * compound)
                                    pnl += loss_amt
                                    balance += loss_amt
                                    sl_sell_count += 1
                                    last_sell_loss_entry = entry
                                    print(f"  -> {datetime.fromtimestamp(rates[j]['time']).strftime('%Y-%m-%d %H:%M')} CLOSED LOSS (Guard: {sl_sell_count})")
                                    all_trades_log.append({
                                        "Time (BKK)": dt_str,
                                        "Close Time": datetime.fromtimestamp(rates[j]['time']).strftime('%Y-%m-%d %H:%M'),
                                        "TF": tf_name,
                                        "Type": signal,
                                        "RSI": round(cur_rsi, 1) if not pd.isna(cur_rsi) else 0,
                                        "Trend": cur_trend,
                                        "Dist50": dist_ema50,
                                        "Dist200": dist_ema200,
                                        "ATR": round(cur_atr, 2),
                                        "R:R": rr_ratio,
                                        "Entry": entry,
                                        "SL": sl,
                                        "TP": tp,
                                        "Lot": compound,
                                        "P&L": loss_amt,
                                        "Balance": balance,
                                        "Reason": "SL"
                                    })
                                trades += 1
                                closed = True
                                break
                            elif future_low <= tp:
                                wins += 1
                                trades += 1
                                sl_sell_count = 0 # Reset guard on win
                                win_amt = ((entry - tp) * 10 * compound)
                                pnl += win_amt
                                balance += win_amt
                                print(f"  -> {datetime.fromtimestamp(rates[j]['time']).strftime('%Y-%m-%d %H:%M')} CLOSED WIN")
                                all_trades_log.append({
                                    "Time (BKK)": dt_str,
                                    "Close Time": datetime.fromtimestamp(rates[j]['time']).strftime('%Y-%m-%d %H:%M'),
                                    "TF": tf_name,
                                    "Type": signal,
                                    "RSI": round(cur_rsi, 1) if not pd.isna(cur_rsi) else 0,
                                    "Trend": cur_trend,
                                    "Dist50": dist_ema50,
                                    "Dist200": dist_ema200,
                                    "ATR": round(cur_atr, 2),
                                    "R:R": rr_ratio,
                                    "Entry": entry,
                                    "SL": sl,
                                    "TP": tp,
                                    "Lot": compound,
                                    "P&L": win_amt,
                                    "Balance": balance,
                                    "Reason": "TP"
                                })
                                closed = True
                                break
                                
                            if not be_active and future_low <= be_trigger:
                                be_active = True
                                sl = entry
                                
                    if not closed:
                        print(f"  -> TRADE LEFT OPEN AT END OF DATA")
                        all_trades_log.append({
                            "Time (BKK)": dt_str,
                            "Close Time": "",
                            "TF": tf_name,
                            "Type": signal,
                            "RSI": round(cur_rsi, 1) if not pd.isna(cur_rsi) else 0,
                            "Trend": cur_trend,
                            "Dist50": dist_ema50,
                            "Dist200": dist_ema200,
                            "ATR": round(cur_atr, 2),
                            "R:R": rr_ratio,
                            "Entry": entry,
                            "SL": sl,
                            "TP": tp,
                            "Lot": compound,
                            "P&L": 0.0,
                            "Balance": balance,
                            "Reason": "OPEN"
                        })
                            
            win_rate = (wins / trades * 100) if trades > 0 else 0
            pnl_str = f"${pnl:,.2f}"
            print(f"| **{tf_name}** | {trades} | {wins} | {losses} | {win_rate:.2f}% | MIX | {pnl_str} |")
            
            total_trades += trades
            total_wins += wins
            total_losses += losses
            total_pnl += pnl
            
        total_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        total_pnl_str = f"${total_pnl:,.2f}"
        print(f"| **สรุปรวมทุก TF** | {total_trades} | {total_wins} | {total_losses} | {total_win_rate:.2f}% | BUY | {total_pnl_str} |")
        
        # Export to CSV
        if all_trades_log:
            import os
            excel_dir = os.path.join(os.path.dirname(__file__), "..", "excel")
            os.makedirs(excel_dir, exist_ok=True)
            csv_path = os.path.join(excel_dir, "s20_13_sim_trades.csv")
            df_trades = pd.DataFrame(all_trades_log)
            # Format to 2 decimal places
            float_cols = ['RSI', 'R:R', 'Entry', 'SL', 'TP', 'Lot', 'P&L', 'Balance']
            for col in float_cols:
                df_trades[col] = df_trades[col].round(2)
            # Ensure columns match s20.12 format
            df_trades.to_csv(csv_path, index=False)
            print(f"\nExported {len(all_trades_log)} trades to {csv_path}")
        
    mt5.shutdown()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--tf", type=str, default="all")
    parser.add_argument("--compound", type=float, default=1.0)
    args = parser.parse_args()
    
    if args.tf == "all":
        tf_list = ["all"]
    else:
        tf_list = [t.strip() for t in args.tf.split(",")]
    
    run_backtest(args.days, tf_list, args.compound)
