import sys
import os
import pandas as pd
import MetaTrader5 as mt5
import itertools
from datetime import datetime

sys.path.append(os.path.abspath(r'd:\Project\Copter01_AI_Bot_2'))
import config
from sim_s30_backtest import fetch_bars
import strategy97

def simulate(all_bars, cfg, lookback=100, spread=0.20):
    trades = []
    last_trade_idx = -100
    
    for i in range(lookback, len(all_bars) - 1):
        if i - last_trade_idx < 10:
            continue
            
        rates_slice = all_bars[i-lookback+1 : i+1]
        sig = strategy97.detect_s97(rates_slice, tf="", cfg=cfg)
        
        if sig and sig.get("signal") in ["BUY", "SELL"]:
            direction = sig["signal"]
            entry = sig["entry"]
            sl = sig["sl"]
            tp = sig["tp"]
            
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
                usd = diff - spread
                trades.append({
                    'outcome': outcome,
                    'profit': usd
                })
                
    return trades

def run_grid():
    SYMBOL = "XAUUSD.iux"
    TF = "M5"
    DAYS = 60
    
    if not config.mt5_initialize(mt5):
        print("MT5 init failed")
        sys.exit(1)

    all_bars = fetch_bars(SYMBOL, TF, DAYS, extra_bars=200)
    mt5.shutdown()

    if all_bars is None or len(all_bars) == 0:
        print("Failed to fetch")
        return
        
    print(f"Loaded {len(all_bars)} bars for Grid Search (Last {DAYS} days)")

    # Grid
    wicks = [0.35, 0.4]
    rrs = [1.0, 1.2, 1.5, 2.0]
    sl_mults = [0.2, 0.5]
    poc_tols = [0.2, 0.5]
    
    combinations = list(itertools.product(wicks, rrs, sl_mults, poc_tols))
    print(f"Testing {len(combinations)} combinations...")
    
    best_net = -99999
    best_cfg = None
    results = []

    for idx, (w, r, sl, pt) in enumerate(combinations):
        cfg = {
            "WICK_RATIO": w,
            "RR": r,
            "SL_MULT": sl,
            "POC_TOL": pt
        }
        
        trades = simulate(all_bars, cfg)
        if not trades:
            continue
            
        win = sum(1 for t in trades if t['outcome'] == 'TP')
        total = sum(t['profit'] for t in trades)
        wr = win / len(trades) * 100
        
        # We want >= 20 trades per month
        if len(trades) >= 20:
            results.append((total, wr, len(trades), cfg))
            if total > best_net:
                best_net = total
                best_cfg = cfg
        
        # print progress
        if idx % 5 == 0:
            print(f"[{idx+1}/{len(combinations)}] Tested W={w} R={r} SL={sl} PT={pt} -> Net: ${total:.2f} WR: {wr:.2f}% Trades: {len(trades)}")

    print("\n=== GRID SEARCH RESULTS (TOP 5) ===")
    results.sort(key=lambda x: x[0], reverse=True)
    for res in results[:5]:
        total, wr, count, c = res
        print(f"Net: ${total:.2f} | WR: {wr:.2f}% | Trades: {count} | CFG: {c}")

if __name__ == "__main__":
    run_grid()
