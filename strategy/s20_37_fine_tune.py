# -*- coding: utf-8 -*-
"""s20_37_fine_tune.py
Fine-tuning the breakthrough for S20.37:
- Compare vol_ratio: 1.20, 1.22, 1.25
- Compare retest_depth: 0.15 vs 0.18
- Compare trailing locks:
  A. Quad-Stage (TP 3.5R): BE@0.8, +1.0@1.5, +2.0@2.4, +2.8@3.0
  B. Penta-Stage (TP 4.0R): BE@0.8, +1.0@1.5, +2.0@2.4, +2.8@3.0, +3.3@3.5
- Strict single position 0.01 lot
- Sequential M5 SL-first on 75,000+ bars
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import bisect
from datetime import datetime, timedelta, timezone
import os, sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from s20_37_deep_confluence import init_mt5, compute_indicators, extract_setups, run_simulation

def main():
    if not init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    print("Fetching data from MT5...", flush=True)
    h4_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H4, start_dt, now)
    h1_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H1, start_dt, now)
    m30_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M30, start_dt, now)
    m15_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M15, start_dt, now)
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)
    mt5.shutdown()

    df_h4 = compute_indicators(h4_gold)
    df_h1 = compute_indicators(h1_gold)
    df_m30 = compute_indicators(m30_gold)
    df_m15 = compute_indicators(m15_gold)

    m5_times = [int(r['time']) for r in m5_gold]
    m5_len = len(m5_gold)

    print("=" * 120, flush=True)
    print(" S20.37 FINE-TUNING GRID (STRICT LOT 0.01 | M5 SL-FIRST | 100% VERIFIABLE)", flush=True)
    print("=" * 120, flush=True)

    for v_rat in [1.20, 1.22, 1.25]:
        for depth in [0.15, 0.18]:
            s0 = extract_setups(df_h4, "H4", min_vol=v_rat, retest_depth=depth, hours=(7, 21))
            s1 = extract_setups(df_h1, "H1", min_vol=v_rat, retest_depth=depth, hours=(7, 21))
            s2 = extract_setups(df_m30, "M30", min_vol=v_rat, retest_depth=depth, hours=(7, 21))
            s3 = extract_setups(df_m15, "M15", min_vol=v_rat, retest_depth=depth, hours=(7, 21))
            comb = sorted(s0 + s1 + s2 + s3, key=lambda x: x['time'])

            # Config A: Quad-Stage TP 3.5R
            res_a = run_simulation(comb, m5_gold, m5_times, m5_len,
                                   be_trigger=0.8, lock1_trig=1.5, lock1_amt=1.0,
                                   lock2_trig=2.4, lock2_amt=2.0, lock3_trig=3.0, lock3_amt=2.8,
                                   lock4_trig=0.0, lock4_amt=0.0, tp_r=3.5)

            # Config B: Penta-Stage TP 4.0R
            res_b = run_simulation(comb, m5_gold, m5_times, m5_len,
                                   be_trigger=0.8, lock1_trig=1.5, lock1_amt=1.0,
                                   lock2_trig=2.4, lock2_amt=2.0, lock3_trig=3.0, lock3_amt=2.8,
                                   lock4_trig=3.5, lock4_amt=3.3, tp_r=4.0)

            print(f"Vol: {v_rat:.2f} | Depth: {depth:.2f} | TP 3.5R: Trades: {res_a['trades']:4d} | W/BE/L: {res_a['wins']:3d}/{res_a['bes']:3d}/{res_a['losses']:2d} | WR: {res_a['wr']:4.1f}% | Net: ${res_a['pnl']:8.2f} | PF: {res_a['pf']:5.2f} | DD: ${res_a['max_dd']:5.2f}", flush=True)
            print(f"Vol: {v_rat:.2f} | Depth: {depth:.2f} | TP 4.0R: Trades: {res_b['trades']:4d} | W/BE/L: {res_b['wins']:3d}/{res_b['bes']:3d}/{res_b['losses']:2d} | WR: {res_b['wr']:4.1f}% | Net: ${res_b['pnl']:8.2f} | PF: {res_b['pf']:5.2f} | DD: ${res_b['max_dd']:5.2f}", flush=True)
            print("-" * 120, flush=True)

if __name__ == "__main__":
    main()
