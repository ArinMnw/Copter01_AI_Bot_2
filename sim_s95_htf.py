import pandas as pd
import MetaTrader5 as mt5
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(r'd:\Project\Copter01_AI_Bot_2'))
import config
from sim_s30_backtest import fetch_bars
import strategy95

def main():
    if not config.mt5_initialize(mt5):
        print("MT5 init failed")
        return
        
    SYMBOL = "XAUUSD.iux"
    TF = "M5"
    DAYS = 30
    SPREAD = 0.20
    LOOKBACK = 200
    
    all_bars = fetch_bars(SYMBOL, TF, DAYS, extra_bars=300)
    mt5.shutdown()
    
    if len(all_bars) == 0: return
    
    # Pre-calculate EMA600 (approx H1 EMA50)
    all_closes = pd.Series([b['close'] for b in all_bars])
    ema600_series = all_closes.ewm(span=600, adjust=False).mean()
    
    trades = []
    last_trade_idx = -100
    
    for i in range(LOOKBACK, len(all_bars) - 1):
        if i - last_trade_idx < 10: continue
            
        rates_slice = all_bars[i-LOOKBACK+1 : i+1]
        # Extract dt_bkk from the last bar in the slice
        dt_bkk = datetime.fromtimestamp(rates_slice[-1]['time'])
        
        # Original S95
        sig = strategy95.detect_s95(rates_slice, tf=TF, dt_bkk=dt_bkk)
        if not sig or sig.get("signal") not in ["BUY", "SELL"]:
            continue
            
        # Check HTF Trend
        ema600 = ema600_series.iloc[i-1]
        ema600_prev = ema600_series.iloc[i-11]
        trend_up = ema600 > ema600_prev
        trend_down = ema600 < ema600_prev
        
        direction = sig["signal"]
        
        # Apply HTF Filter: only trade in direction of H1 trend
        if direction == "BUY" and not trend_up: continue
        if direction == "SELL" and not trend_down: continue
            
        entry = sig["entry"]
        sl = sig["sl"]
        tp = sig["tp"]
        
        # Forward simulate
        outcome = "OPEN"
        exit_price = 0
        for j in range(i+1, len(all_bars)):
            h = all_bars[j]['high']
            l = all_bars[j]['low']
            if direction == "BUY":
                if l <= sl:
                    outcome, exit_price = "SL", sl
                    break
                elif h >= tp:
                    outcome, exit_price = "TP", tp
                    break
            else:
                if h >= sl:
                    outcome, exit_price = "SL", sl
                    break
                elif l <= tp:
                    outcome, exit_price = "TP", tp
                    break
                    
        if outcome != "OPEN":
            last_trade_idx = i
            diff = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
            usd = diff - SPREAD
            trades.append(usd)
            
    win = len([t for t in trades if t > 0])
    loss = len([t for t in trades if t <= 0])
    total = len(trades)
    wr = win/total*100 if total > 0 else 0
    net = sum(trades)
    
    print(f"--- S95 with HTF Trend Filter ---")
    print(f"Trades: {total}, Win: {win}, Loss: {loss}")
    print(f"Win Rate: {wr:.2f}%")
    print(f"Net Profit: ${net:.2f}")

if __name__ == "__main__":
    main()
