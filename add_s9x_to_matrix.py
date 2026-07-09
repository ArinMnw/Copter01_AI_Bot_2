import numpy as np
import json
import csv
from datetime import datetime
import MetaTrader5 as mt5

import config
import sim_s30_backtest as s30sim
from strategy95 import strategy_95
from strategy96 import strategy_96
from strategy97 import strategy_97
from optimize_s75_champion_formula import _simulate_leg
from optimize_s88_allin4s_fast import OVERLAY_CFG

def run_strategy(strategy_fn, bars, tf):
    trades = []
    n = len(bars)
    for j in range(100, n - 1):
        slice_bars = bars[j-100:j+1]
        sig = strategy_fn(slice_bars, tf=tf)
        if sig is None or sig.get("signal") not in ("BUY", "SELL"):
            continue
            
        direction = sig["signal"]
        entry = float(sig["entry"])
        sl = float(sig["sl"])
        tp = float(sig["tp"])
        fill_idx = j + 1
        
        outcome, exit_price, exit_idx = "OPEN", None, None
        for m in range(fill_idx, n):
            hi = float(bars[m]["high"])
            lw = float(bars[m]["low"])
            if direction == "BUY":
                if lw <= sl:
                    outcome, exit_price = "SL", sl
                elif hi >= tp:
                    outcome, exit_price = "TP", tp
            else:
                if hi >= sl:
                    outcome, exit_price = "SL", sl
                elif lw <= tp:
                    outcome, exit_price = "TP", tp
            if outcome != "OPEN":
                exit_idx = m
                break
                
        if outcome == "OPEN":
            continue
            
        risk_distance = abs(entry - sl)
        diff = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
        trades.append({
            "signal": direction,
            "outcome": outcome,
            "signal_time_ts": int(bars[j]["time"]),
            "fill_time_ts": int(bars[fill_idx]["time"]),
            "exit_time_ts": int(bars[exit_idx]["time"]),
            "entry": round(entry, 2),
            "tp": round(tp, 2),
            "sl": round(sl, 2),
            "exit_price": round(exit_price, 2),
            "risk_distance": round(risk_distance, 4),
            "diff_usd_per_001lot": round(diff, 4),
            "spread": 0.20,
            "reason": sig["reason"],
        })
    return trades

def main():
    if not config.mt5_initialize(mt5):
        print("MT5 initialize failed")
        return
        
    days = 550
    tfs = {
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1
    }
    
    strategies = {
        "S95": strategy_95,
        "S96": strategy_96,
        "S97": strategy_97
    }
    
    # Load alignment dates
    dates = []
    with open("lts0_empty_daily.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row["days"]) == 550:
                dates.append(row["date"])
    dates_idx = {d: i for i, d in enumerate(dates)}
    
    new_vectors = []
    new_labels = []
    
    try:
        for tf_str, tf_mt5 in tfs.items():
            print(f"Fetching {tf_str} for {config.SYMBOL}...")
            bars = s30sim.fetch_bars(config.SYMBOL, tf_str, days, extra_bars=700)
            
            for s_name, s_fn in strategies.items():
                print(f"Running {s_name} on {tf_str}...")
                raw_trades = run_strategy(s_fn, bars, tf=tf_str)
                print(f"{s_name}_{tf_str} generated {len(raw_trades)} trades")
                
                if len(raw_trades) > 0:
                    _twp, _eq, by_day = _simulate_leg(raw_trades, OVERLAY_CFG)
                    pnl_vec = np.zeros(len(dates), dtype=float)
                    for d, pnl in by_day.items():
                        if d in dates_idx:
                            pnl_vec[dates_idx[d]] = float(pnl)
                            
                    new_vectors.append(pnl_vec)
                    new_labels.append(f"DIRECT_{s_name}_{tf_str}")
                    
                    # Also add INVERSE
                    inverse_trades = []
                    for t in raw_trades:
                        it = dict(t)
                        it["signal"] = "SELL" if t["signal"] == "BUY" else "BUY"
                        it["diff_usd_per_001lot"] = -t["diff_usd_per_001lot"]
                        it["outcome"] = "TP" if t["outcome"] == "SL" else "SL"
                        inverse_trades.append(it)
                    
                    _twp_inv, _eq_inv, by_day_inv = _simulate_leg(inverse_trades, OVERLAY_CFG)
                    pnl_vec_inv = np.zeros(len(dates), dtype=float)
                    for d, pnl in by_day_inv.items():
                        if d in dates_idx:
                            pnl_vec_inv[dates_idx[d]] = float(pnl)
                            
                    new_vectors.append(pnl_vec_inv)
                    new_labels.append(f"INVERSE_{s_name}_{tf_str}")
    finally:
        mt5.shutdown()
        
    print("Loading original matrix...")
    P_matrix = np.load("lts_P_matrix.npy")
    W_orig = np.load("lts_W_orig.npy")
    with open("lts_leg_labels.json", "r") as f:
        leg_labels = json.load(f)
        
    # Append new
    if new_vectors:
        P_new = np.vstack(new_vectors).T # shape: (550, len(new_vectors))
        P_matrix = np.hstack([P_matrix, P_new])
        W_orig = np.concatenate([W_orig, np.zeros(len(new_vectors))])
        leg_labels.extend(new_labels)
        
        np.save("lts_P_matrix_ext.npy", P_matrix)
        np.save("lts_W_orig_ext.npy", W_orig)
        with open("lts_leg_labels_ext.json", "w") as f:
            json.dump(leg_labels, f)
            
        print(f"Appended {len(new_vectors)} new legs.")
        print(f"New matrix shape: {P_matrix.shape}")
        print("Saved to *_ext files.")
    else:
        print("No new vectors generated.")

if __name__ == "__main__":
    main()
