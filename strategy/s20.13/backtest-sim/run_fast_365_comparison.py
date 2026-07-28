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

def run_comp(days=365, symbol="XAUUSD.iux", compound=1.5):
    path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
    if not mt5.initialize(path=path): return
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start_time, end_time)
    
    df_master = compute_indicators_df(rates)
    
    # Run v20 fast
    wins20, losses20, be20, trades20, pnl20 = 0, 0, 0, 0, 0.0
    sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
    
    for i in range(100, len(rates) - 10):
        res = evaluate_bar(df_master, i, tf="H1")
        if res and res.get("signal") in ["BUY", "SELL"]:
            signal = res["signal"]; entry = res["entry"]; sl = res["sl"]; tp = res["tp"]
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
                            losses20 += 1; pnl20 -= ((entry - sl) * 10 * compound)
                            sl_buy_count += 1; last_buy_loss = entry
                        trades20 += 1; break
                    elif f_bar['high'] >= tp:
                        wins20 += 1; trades20 += 1; sl_buy_count = 0
                        pnl20 += ((tp - entry) * 10 * compound); break
                    if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                elif signal == "SELL":
                    if f_bar['high'] >= sl:
                        if be_act: be20 += 1
                        else:
                            losses20 += 1; pnl20 -= ((sl - entry) * 10 * compound)
                            sl_sell_count += 1; last_sell_loss = entry
                        trades20 += 1; break
                    elif f_bar['low'] <= tp:
                        wins20 += 1; trades20 += 1; sl_sell_count = 0
                        pnl20 += ((entry - tp) * 10 * compound); break
                    if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry

    # Run v19 by checking without v20 filters
    wins19, losses19, be19, trades19, pnl19 = 0, 0, 0, 0, 0.0
    sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
    
    for i in range(100, len(rates) - 10):
        # Check v19 logic using df_master
        cur = df_master.iloc[i]; prev = df_master.iloc[i-1]
        lookback = df_master.iloc[i-14:i-3]; r3 = df_master.iloc[i-3:i]
        local_low = lookback['low'].min(); local_high = lookback['high'].max()
        hr = cur['time_dt'].hour
        is_strong = (cur['high'] - cur['low']) >= (0.8 * cur['atr'])
        
        sig = "WAIT"
        # BUY check
        if ((r3['low'].min() < local_low and cur['close'] > prev['high']) or (cur['low'] < local_low and cur['close'] > prev['high'])):
            if is_strong and hr not in [12,13,23,0,2,19,17,8,9] and cur['rsi'] >= 35:
                if not (cur['z_score'] > 0.0 and cur['adx'] > 30.0) and cur['adx'] <= 52.0 and not (cur['atr_pct'] <= 0.41 and cur['adx'] < 50.0):
                    sig = "BUY"
                    entry = cur['close']
                    sl = min(r3['low'].min(), cur['low']) - (cur['atr'] * 0.25)
                    tp = min(r3['low'].min(), cur['low']) + (cur['atr'] * 2.6 * np.sqrt(720/60))
        # SELL check
        if sig == "WAIT" and ((r3['high'].max() > local_high and cur['close'] < prev['low']) or (cur['high'] > local_high and cur['close'] < prev['low'])):
            if is_strong and hr not in [12,13,23,0,8,9] and cur['rsi'] <= 60:
                if not ((cur['z_score'] < 0.0 and cur['adx'] > 50.0) or (cur['close'] - cur['ema_50'] > 100.0)):
                    if not (cur['rsi_7'] > 50.5 and 0.35 <= cur['body_pct'] <= 0.615):
                        if not (cur['rsi_7'] > 50.5 and 0.35 <= cur['body_pct'] <= 0.65 and cur['di_diff'] < 4.0):
                            if not (cur['vol_ratio'] < 0.88 and cur['di_diff'] > 1.0):
                                if not (cur['body_pct'] < 0.145) and not (cur['rsi'] < 37.0 and cur['z_score'] > -1.80):
                                    if not (cur['adx'] < 17.5 and cur['vol_ratio'] < 0.90) and not (cur['rsi'] > 58.5 and cur['rsi_7'] < 41.5):
                                        sig = "SELL"
                                        entry = cur['close']
                                        sl = max(r3['high'].max(), cur['high']) + (cur['atr'] * 0.25)
                                        tp = max(r3['high'].max(), cur['high']) - (cur['atr'] * 2.6 * np.sqrt(1440/60))
                                        
        if sig in ["BUY", "SELL"]:
            if sig == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
            if sig == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
            
            future_rates = rates[i+1:]
            be_trig = entry + ((tp - entry) * 0.4) if sig == "BUY" else entry - ((entry - tp) * 0.4)
            be_act = False
            for f_bar in future_rates:
                if sig == "BUY":
                    if f_bar['low'] <= sl:
                        if be_act: be19 += 1
                        else:
                            losses19 += 1; pnl19 -= ((entry - sl) * 10 * compound)
                            sl_buy_count += 1; last_buy_loss = entry
                        trades19 += 1; break
                    elif f_bar['high'] >= tp:
                        wins19 += 1; trades19 += 1; sl_buy_count = 0
                        pnl19 += ((tp - entry) * 10 * compound); break
                    if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                elif sig == "SELL":
                    if f_bar['high'] >= sl:
                        if be_act: be19 += 1
                        else:
                            losses19 += 1; pnl19 -= ((sl - entry) * 10 * compound)
                            sl_sell_count += 1; last_sell_loss = entry
                        trades19 += 1; break
                    elif f_bar['low'] <= tp:
                        wins19 += 1; trades19 += 1; sl_sell_count = 0
                        pnl19 += ((entry - tp) * 10 * compound); break
                    if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry
                    
    print("\n================== 365-DAY (1 YEAR) COMPARISON (Compound=1.5) ==================")
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
    run_comp()
