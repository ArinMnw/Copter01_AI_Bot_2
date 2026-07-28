import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import argparse
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from strategy20_13_23 import compute_indicators_df, evaluate_bar
import config

def run_backtest_23(days=700, symbol="XAUUSD.iux", tf_str="H1", compound=1.5):
    path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
    if not mt5.initialize(path=path):
        print("Failed to initialize MT5")
        return
        
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start_time, end_time)
    
    if rates is None or len(rates) == 0:
        print("No rates found!")
        mt5.shutdown()
        return

    df_master = compute_indicators_df(rates)
    df_master['upper_wick'] = df_master['high'] - np.maximum(df_master['open'], df_master['close'])
    df_master['lower_wick'] = np.minimum(df_master['open'], df_master['close']) - df_master['low']
    df_master['upper_wick_pct'] = df_master['upper_wick'] / (df_master['range'] + 0.0001)
    df_master['lower_wick_pct'] = df_master['lower_wick'] / (df_master['range'] + 0.0001)
    df_master['dist_ema50'] = df_master['close'] - df_master['ema_50']
    df_master['dist_ema200'] = df_master['close'] - df_master['ema_200']
    df_master['hour'] = df_master['time_dt'].dt.hour

    wins, losses, be, trades, pnl = 0, 0, 0, 0, 0.0
    sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
    all_trades_log = []
    
    for i in range(100, len(rates) - 10):
        res = evaluate_bar(df_master, i, tf=tf_str)
        if res and res.get("signal") in ["BUY", "SELL"]:
            signal = res["signal"]; entry = res["entry"]; sl = res["sl"]; tp = res["tp"]
            
            if signal == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
            if signal == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
            
            dt_str = datetime.fromtimestamp(rates[i]['time']).strftime('%Y-%m-%d %H:%M:%S')
            future_rates = rates[i+1:]
            be_trig = entry + ((tp - entry) * 0.4) if signal == "BUY" else entry - ((entry - tp) * 0.4)
            be_act = False
            closed = False
            
            for f_bar in future_rates:
                if signal == "BUY":
                    if f_bar['low'] <= sl:
                        if be_act: be += 1
                        else:
                            losses += 1; pnl -= ((entry - sl) * 10 * compound)
                            sl_buy_count += 1; last_buy_loss = entry
                        trades += 1; closed = True
                        all_trades_log.append({"Time": dt_str, "Type": signal, "Entry": entry, "SL": sl, "TP": tp, "Result": "BE" if be_act else "LOSS", "PnL": 0 if be_act else -((entry - sl) * 10 * compound)})
                        break
                    elif f_bar['high'] >= tp:
                        wins += 1; trades += 1; sl_buy_count = 0
                        pnl += ((tp - entry) * 10 * compound)
                        closed = True
                        all_trades_log.append({"Time": dt_str, "Type": signal, "Entry": entry, "SL": sl, "TP": tp, "Result": "WIN", "PnL": ((tp - entry) * 10 * compound)})
                        break
                    if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                elif signal == "SELL":
                    if f_bar['high'] >= sl:
                        if be_act: be += 1
                        else:
                            losses += 1; pnl -= ((sl - entry) * 10 * compound)
                            sl_sell_count += 1; last_sell_loss = entry
                        trades += 1; closed = True
                        all_trades_log.append({"Time": dt_str, "Type": signal, "Entry": entry, "SL": sl, "TP": tp, "Result": "BE" if be_act else "LOSS", "PnL": 0 if be_act else -((sl - entry) * 10 * compound)})
                        break
                    elif f_bar['low'] <= tp:
                        wins += 1; trades += 1; sl_sell_count = 0
                        pnl += ((entry - tp) * 10 * compound)
                        closed = True
                        all_trades_log.append({"Time": dt_str, "Type": signal, "Entry": entry, "SL": sl, "TP": tp, "Result": "WIN", "PnL": ((entry - tp) * 10 * compound)})
                        break
                    if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry

    win_rate_wl = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    df_log = pd.DataFrame(all_trades_log)
    csv_path = os.path.join(os.path.dirname(__file__), "s20_13_23_trades.csv")
    df_log.to_csv(csv_path, index=False)
    
    sniper_count = 0
    if len(df_log) > 0:
        sniper_count = len(df_log[(df_log['Time'].str.contains('2026-07-16|2026-07-17')) & (df_log['Type'] == 'BUY')])
        
    print("\n================== STRATEGY 20.13.23 (700 DAYS) ==================")
    print(f"Timeframe: {tf_str} | Days: {days} | Symbol: {symbol}")
    print(f"Total Trades: {trades} | Wins: {wins} | Losses: {losses} | BE: {be}")
    print(f"Win Rate (Win/Loss): {win_rate_wl:.2f}% (Target: >= 80%)")
    print(f"Net Profit ($): ${pnl:,.2f} (Target: >= $150k)")
    print(f"Mid-July Sniper BUYs: {sniper_count} / 3")
    print(f"Trades saved to: {csv_path}")
    
    mt5.shutdown()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=700)
    parser.add_argument("--tf", type=str, default="H1")
    parser.add_argument("--compound", type=float, default=1.5)
    args = parser.parse_args()
    run_backtest_23(days=args.days, tf_str=args.tf, compound=args.compound)
