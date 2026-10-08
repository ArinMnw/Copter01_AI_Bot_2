# -*- coding: utf-8 -*-
import sys
import os
import json
import warnings
warnings.filterwarnings('ignore')

root_dir = r"d:\Project\Copter01_AI_Bot_2"
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, "strategy"))

import backtest_s20_unified as btu
from goal_s20_53_to_100 import init_mt5
import MetaTrader5 as mt5

init_mt5()

# Symbols
symbols = ["XAUUSD.iux", "XAGUSD.iux", "EURUSD.iux", "GBPUSD.iux", "USDJPY.iux"]

print("=== STARTING GRID SEARCH FOR S20 NEGATIVE STRATEGIES ===")

# Test S20.18, S20.21, S20.22, S20.28, S20.301, S20.304
target_sids = [20.18, 20.21, 20.22, 20.28, 20.301, 20.304]

# We will sweep S20_TUNE_PARAMS env var or modify _S20_TUNE in btu directly
results = {}

for sid in target_sids:
    print(f"\n==================== TUNING S{sid} ====================")
    best_pnl = -999999
    best_param = None
    
    for tp_r in [1.2, 1.5, 1.8, 2.0, 2.5, 3.0, 4.0, 5.0]:
        btu._S20_TUNE = {sid: {"tp_r": tp_r}}
        
        # Run unified backtest for this strategy across 5 symbols
        total_pnl = 0.0
        total_trades = 0
        total_wins = 0
        
        for sym in symbols:
            # fetch rates
            digits = 2 if "XAU" in sym or "JPY" in sym else (3 if "XAG" in sym else 5)
            point = 0.01 if "XAU" in sym or "JPY" in sym else (0.001 if "XAG" in sym else 0.00001)
            
            rates_by_tf = {}
            for tf in ['H4', 'H1', 'M30', 'M15', 'M5', 'M1']:
                tf_const = getattr(mt5, f"TIMEFRAME_{tf}")
                r = mt5.copy_rates_from_pos(sym, tf_const, 0, 45000 if tf in ('M5', 'M1') else 15000)
                if r is not None and len(r) > 0:
                    rates_by_tf[tf] = r
            
            if "M5" not in rates_by_tf:
                continue
                
            setups = btu.extract_setups_for_strategy(sid, sym, rates_by_tf, digits, point)
            
            # Lot size matching unified backtest: Gold/Silver=0.01, GBP=0.11, EUR/JPY=0.14
            lot = 0.01 if "XAU" in sym or "XAG" in sym else (0.11 if "GBP" in sym else 0.14)
            c_size = 100.0 if "XAU" in sym else (5000.0 if "XAG" in sym else 100000.0)
            
            m5_bars = rates_by_tf["M5"]
            m5_times = [int(r['time']) for r in m5_bars]
            m1_bars = rates_by_tf.get("M1")
            m1_times = [int(r['time']) for r in m1_bars] if m1_bars is not None else None
            
            trades = btu.simulate_strategy_trades(
                sid=sid, symbol=sym, m5_bars=m5_bars, m5_times=m5_times,
                setups=setups, lot=lot, contract_size=c_size, digits=digits,
                concurrent=True, m1_bars=m1_bars, m1_times=m1_times
            )
            
            sym_pnl = sum(t["pnl_usd"] for t in trades)
            sym_wins = sum(1 for t in trades if t["outcome"] == "TP")
            total_pnl += sym_pnl
            total_trades += len(trades)
            total_wins += sym_wins
            
        wr = (total_wins / total_trades * 100) if total_trades > 0 else 0.0
        print(f"S{sid} | tp_r={tp_r:3.1f} | Trades={total_trades:4d} | WR={wr:5.1f}% | Net PnL=${total_pnl:+10.2f}")
        
        if total_pnl > best_pnl:
            best_pnl = total_pnl
            best_param = (tp_r, total_trades, wr, total_pnl)
            
    results[sid] = best_param

mt5.shutdown()

print("\n==================== SUMMARY OF BEST TP_R ====================")
for sid, res in results.items():
    if res:
        print(f"S{sid:6.3f}: Best tp_r={res[0]} | Trades={res[1]} | WR={res[2]:.1f}% | Net PnL=${res[3]:+.2f}")
