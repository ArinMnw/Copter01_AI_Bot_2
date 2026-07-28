import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from strategy20_13_19 import strategy_20_13_19
from strategy20_13_20 import compute_indicators_df, evaluate_bar

def compare_runs(days=365, symbol="XAUUSD.iux"):
    path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
    if not mt5.initialize(path=path):
        print("MT5 initialize failed")
        return
        
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start_time, end_time)
    print(f"Loaded {len(rates)} H1 bars for {days} days ({symbol})")
    
    df_master = compute_indicators_df(rates)
    
    # 1. Simulate v19
    wins19, losses19, be19, trades19, pnl19 = 0, 0, 0, 0, 0.0
    sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
    
    for i in range(100, len(rates) - 10):
        # We pass 250 bars window to v19 for speed
        res = strategy_20_13_19(rates[max(0, i-250):i+1], tf="H1")
        if res and res.get("signal") in ["BUY", "SELL"]:
            signal = res["signal"]
            entry, sl, tp = res["entry"], res["sl"], res["tp"]
            
            if signal == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
            if signal == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
            
            future_rates = rates[i+1:]
            be_trig = entry + ((tp - entry) * 0.4) if signal == "BUY" else entry - ((entry - tp) * 0.4)
            be_act = False
            
            for f_bar in future_rates:
                if signal == "BUY":
                    if f_bar['low'] <= sl:
                        if be_act: be19 += 1
                        else:
                            losses19 += 1
                            pnl19 -= ((entry - sl) * 10)
                            sl_buy_count += 1; last_buy_loss = entry
                        trades19 += 1; break
                    elif f_bar['high'] >= tp:
                        wins19 += 1; trades19 += 1; sl_buy_count = 0
                        pnl19 += ((tp - entry) * 10); break
                    if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                elif signal == "SELL":
                    if f_bar['high'] >= sl:
                        if be_act: be19 += 1
                        else:
                            losses19 += 1
                            pnl19 -= ((sl - entry) * 10)
                            sl_sell_count += 1; last_sell_loss = entry
                        trades19 += 1; break
                    elif f_bar['low'] <= tp:
                        wins19 += 1; trades19 += 1; sl_sell_count = 0
                        pnl19 += ((entry - tp) * 10); break
                    if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry

    # 2. Simulate v20
    wins20, losses20, be20, trades20, pnl20 = 0, 0, 0, 0, 0.0
    sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
    
    for i in range(100, len(rates) - 10):
        res = evaluate_bar(df_master, i, tf="H1")
        if res and res.get("signal") in ["BUY", "SELL"]:
            signal = res["signal"]
            entry, sl, tp = res["entry"], res["sl"], res["tp"]
            
            if signal == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
            if signal == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
            
            future_rates = rates[i+1:]
            be_trig = entry + ((tp - entry) * 0.4) if signal == "BUY" else entry - ((entry - tp) * 0.4)
            be_act = False
            
            for f_bar in future_rates:
                if signal == "BUY":
                    if f_bar['low'] <= sl:
                        if be_act: be20 += 1
                        else:
                            losses20 += 1
                            pnl20 -= ((entry - sl) * 10)
                            sl_buy_count += 1; last_buy_loss = entry
                        trades20 += 1; break
                    elif f_bar['high'] >= tp:
                        wins20 += 1; trades20 += 1; sl_buy_count = 0
                        pnl20 += ((tp - entry) * 10); break
                    if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                elif signal == "SELL":
                    if f_bar['high'] >= sl:
                        if be_act: be20 += 1
                        else:
                            losses20 += 1
                            pnl20 -= ((sl - entry) * 10)
                            sl_sell_count += 1; last_sell_loss = entry
                        trades20 += 1; break
                    elif f_bar['low'] <= tp:
                        wins20 += 1; trades20 += 1; sl_sell_count = 0
                        pnl20 += ((entry - tp) * 10); break
                    if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry
                    
    print("\n================== 365-DAY (1 YEAR) COMPARISON ==================")
    print(f"V19 BASELINE : Trades={trades19} | Win={wins19} | Loss={losses19} | BE={be19}")
    print(f"  -> Classic Win Rate = {(wins19/trades19)*100:.2f}% | Win/Loss Rate = {(wins19/(wins19+losses19))*100:.2f}% | Net P&L = ${pnl19:,.2f}")
    
    print(f"\nV20 EVOLUTION: Trades={trades20} | Win={wins20} | Loss={losses20} | BE={be20}")
    print(f"  -> Classic Win Rate = {(wins20/trades20)*100:.2f}% | Win/Loss Rate = {(wins20/(wins20+losses20))*100:.2f}% | Net P&L = ${pnl20:,.2f}")
    
    print(f"\nIMPROVEMENT:")
    print(f"  -> SL Eliminated : {losses19 - losses20} trades (-{((losses19-losses20)/losses19)*100:.1f}%)")
    print(f"  -> TP Preserved  : {wins20} / {wins19} ({wins20/wins19*100:.1f}%)")
    print(f"  -> P&L Increase  : +${pnl20 - pnl19:,.2f}")

    mt5.shutdown()

if __name__ == "__main__":
    compare_runs()
