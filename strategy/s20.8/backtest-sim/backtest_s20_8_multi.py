"""
Multi-timeframe Backtest for S20.8 Optimization
Runs for 30, 60, 90, 120, 180 days in a single script.
Mutes individual order logs, shows only summary table.
"""
import argparse
import os
import sys
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STRATEGY_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.abspath(os.path.join(STRATEGY_DIR, "..", ".."))
for _path in (REPO_ROOT, STRATEGY_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

BKK = timezone(timedelta(hours=7))

import MetaTrader5 as mt5
import config
import htf_fvg
from strategy20_8 import strategy_20_8

# Force enable strategy
config.S20_8_ENABLED = True
config.active_strategies[20.8] = True
config.S20_TREND_FILTER = False # Prevent Look-ahead Bias

SYMBOL = config.SYMBOL
DEFAULT_SPREAD = 0.20 # Includes spread, slippage, commission roughly per 0.01 lot in USD

TF_MAP = {
    "M1":  (mt5.TIMEFRAME_M1, 1440),
    "M5":  (mt5.TIMEFRAME_M5, 288),
    "M15": (mt5.TIMEFRAME_M15, 96),
    "M30": (mt5.TIMEFRAME_M30, 48),
    "H1":  (mt5.TIMEFRAME_H1, 24),
}

def fetch_bars(symbol, tf_name, days):
    tf_val, per_day = TF_MAP[tf_name]
    count = days * per_day + 300
    rates = mt5.copy_rates_from_pos(symbol, tf_val, 0, count)
    return rates

def replay_tf(bars, tf_name, spread):
    trades = []
    n = len(bars)
    last_signal_bar = {}
    
    for j in range(15, n - 1):
        entry_bar = bars[j]
        rates_slice = bars[max(0, j - 100):j + 1]
        
        res = strategy_20_8(rates_slice, tf=tf_name)
        sig = res.get("signal")
        if sig not in ("BUY", "SELL"):
            continue

        dedup_key = (sig, res.get("pattern", ""))
        if dedup_key in last_signal_bar and j - last_signal_bar[dedup_key] < 3:
            continue
        last_signal_bar[dedup_key] = j

        entry = float(res["entry"])
        tp = float(res["tp"])
        sl = float(res["sl"])
        
        order_mode = res.get("order_mode", "market")
        
        start = j + 1
        fill_idx = None
        
        if order_mode == "market":
            fill_idx = j
        else:
            cancel_bars = 5
            for m in range(j + 1, min(j + 1 + cancel_bars, n)):
                hi = float(bars[m]["high"])
                lw = float(bars[m]["low"])
                if sig == "BUY":
                    if lw <= entry: fill_idx = m; break
                    if hi >= tp: break
                else:
                    if hi >= entry: fill_idx = m; break
                    if lw <= tp: break
        
        if fill_idx is None:
            continue
            
        start = fill_idx
        outcome, exit_price = "OPEN", None
        
        for m in range(start, n):
            hi = float(bars[m]["high"])
            lw = float(bars[m]["low"])
            
            if sig == "BUY":
                if lw <= sl: outcome, exit_price = "SL", sl
                elif hi >= tp: outcome, exit_price = "TP", tp
            else:
                if hi >= sl: outcome, exit_price = "SL", sl
                elif lw <= tp: outcome, exit_price = "TP", tp
                    
            if outcome != "OPEN":
                break
                
        if outcome == "OPEN":
            continue
            
        diff = (exit_price - entry) if sig == "BUY" else (entry - exit_price)
        pnl = diff - spread
        
        trades.append({
            "tf": tf_name, 
            "outcome": outcome,
            "pnl_usd_001lot": round(pnl, 2),
        })
        
    return trades

def summarize(trades):
    closed = [t for t in trades if t["outcome"] in ("TP", "SL")]
    if not closed:
        return {"trades": 0, "wr": 0.0, "pnl": 0.0}
    wins = [t for t in closed if t["pnl_usd_001lot"] > 0]
    pnl = sum(t["pnl_usd_001lot"] for t in closed)
    return {
        "trades": len(closed),
        "wr": round(100.0 * len(wins) / len(closed), 1),
        "pnl": round(pnl, 2),
    }

def main():
    if not config.mt5_initialize(mt5):
        print(f"MT5 initialize failed: {mt5.last_error()}")
        return
        
    print("Fetching HTF FVGs for backtest...")
    htf_fvg.clear_cache()
    htf_fvg.fetch_active_fvgs("D1", SYMBOL, lookback=1000)
    htf_fvg.fetch_active_fvgs("H4", SYMBOL, lookback=5000)
    
    tf_list = ["M1", "M5", "M15"]
    durations = [30, 60, 90, 120, 180]
    spread = DEFAULT_SPREAD
    
    print("\n" + "="*80)
    print(f"{'Days':<10} | {'Total Trades':<15} | {'Win Rate (%)':<15} | {'Net Profit ($)':<15} (per 0.01 lot)")
    print("="*80)
    
    for days in durations:
        all_trades = []
        for tf_name in tf_list:
            bars = fetch_bars(SYMBOL, tf_name, days)
            if bars is not None:
                trades = replay_tf(bars, tf_name, spread)
                all_trades += trades
                
        s = summarize(all_trades)
        print(f"{days:<10} | {s['trades']:<15} | {s['wr']:<15.1f} | {s['pnl']:<15.2f}")
        
    print("="*80)
    mt5.shutdown()

if __name__ == "__main__":
    main()
