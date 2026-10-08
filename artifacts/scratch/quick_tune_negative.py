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

symbols = ["XAUUSD.iux", "XAGUSD.iux", "EURUSD.iux", "GBPUSD.iux", "USDJPY.iux"]
target_sids = [20.18, 20.21, 20.22, 20.28, 20.301, 20.304]

print("=== FAST GRID SEARCH: MARKET ENTRY (entry_mode='MARKET') ===")

cache_data = {}

for sym in symbols:
    digits = 2 if "XAU" in sym or "JPY" in sym else (3 if "XAG" in sym else 5)
    point = 0.01 if "XAU" in sym or "JPY" in sym else (0.001 if "XAG" in sym else 0.00001)
    lot = 0.01 if "XAU" in sym or "XAG" in sym else (0.11 if "GBP" in sym else 0.14)
    c_size = 100.0 if "XAU" in sym else (5000.0 if "XAG" in sym else 100000.0)

    rates_by_tf = {}
    for tf in ['H4', 'H1', 'M30', 'M15', 'M5', 'M1']:
        tf_const = getattr(mt5, f"TIMEFRAME_{tf}")
        r = mt5.copy_rates_from_pos(sym, tf_const, 0, 30000 if tf in ('M5', 'M1') else 10000)
        if r is not None and len(r) > 0:
            rates_by_tf[tf] = r

    m5_bars = rates_by_tf.get("M5")
    m5_times = [int(r['time']) for r in m5_bars] if m5_bars is not None else []
    m1_bars = rates_by_tf.get("M1")
    m1_times = [int(r['time']) for r in m1_bars] if m1_bars is not None else []

    cache_data[sym] = {
        "digits": digits, "point": point, "lot": lot, "c_size": c_size,
        "rates_by_tf": rates_by_tf, "m5_bars": m5_bars, "m5_times": m5_times,
        "m1_bars": m1_bars, "m1_times": m1_times
    }

mt5.shutdown()

print("Rates cached successfully!")

for sid in target_sids:
    print(f"\n==================== TUNING S{sid} (MARKET ENTRY) ====================")
    for tp_r in [1.2, 1.5, 1.8, 2.0, 2.5, 3.0, 4.0]:
        btu._S20_TUNE = {sid: {"tp_r": tp_r, "entry_mode": "MARKET"}}
        total_pnl = 0.0
        total_trades = 0
        total_wins = 0

        for sym in symbols:
            c = cache_data[sym]
            setups = btu.extract_setups_for_strategy(sid, sym, c["rates_by_tf"], c["digits"], c["point"])
            trades = btu.simulate_strategy_trades(
                sid=sid, symbol=sym, m5_bars=c["m5_bars"], m5_times=c["m5_times"],
                setups=setups, lot=c["lot"], contract_size=c["c_size"], digits=c["digits"],
                concurrent=True, m1_bars=c["m1_bars"], m1_times=c["m1_times"]
            )
            total_pnl += sum(t["pnl_usd"] for t in trades)
            total_trades += len(trades)
            total_wins += sum(1 for t in trades if t["outcome"] == "TP")

        wr = (total_wins / total_trades * 100) if total_trades > 0 else 0.0
        print(f"S{sid:6.3f} [MARKET] | tp_r={tp_r:3.1f} | Trades={total_trades:4d} | WR={wr:5.1f}% | Net PnL=${total_pnl:+10.2f}")
