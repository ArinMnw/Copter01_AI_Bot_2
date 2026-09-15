# -*- coding: utf-8 -*-
"""check_s20_40_combined.py
Combine H2 Horizon + Window (3, 22) + Octa-Stage Trailing (TP 5.0R / 4.8R)
"""
import MetaTrader5 as mt5
import pandas as pd
import bisect
from datetime import datetime, timedelta, timezone
import os, sys

sys.path.append(os.path.dirname(__file__))
from s20_40_research import init_mt5, compute_indicators, extract_setups, run_simulation

def main():
    if not init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    h4_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H4, start_dt, now)
    h2_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H2, start_dt, now)
    h1_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H1, start_dt, now)
    m30_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M30, start_dt, now)
    m15_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M15, start_dt, now)
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)
    mt5.shutdown()

    df_h4 = compute_indicators(h4_gold)
    df_h2 = compute_indicators(h2_gold)
    df_h1 = compute_indicators(h1_gold)
    df_m30 = compute_indicators(m30_gold)
    df_m15 = compute_indicators(m15_gold)

    m5_times = [int(r['time']) for r in m5_gold]
    m5_len = len(m5_gold)

    s0 = extract_setups(df_h4, "H4", min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=(3, 22), use_pqh=True)
    s_h2 = extract_setups(df_h2, "H2", min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=(3, 22), use_pqh=True)
    s1 = extract_setups(df_h1, "H1", min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=(3, 22), use_pqh=True)
    s2 = extract_setups(df_m30, "M30", min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=(3, 22), use_pqh=True)
    s3 = extract_setups(df_m15, "M15", min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=(3, 22), use_pqh=True)
    comb = sorted(s0 + s_h2 + s1 + s2 + s3, key=lambda x: x['time'])

    print(f"Total setups detected: {len(comb)}")

    octa_configs = [
        ("Septa TP 4.6R", 0.8, 1.5, 1.0, 2.4, 2.0, 3.0, 2.8, 3.5, 3.3, 3.8, 3.5, 4.2, 3.9, 0.0, 0.0, 4.6),
        ("Octa-A: TP 4.8R (L7@4.5->4.2)", 0.8, 1.5, 1.0, 2.4, 2.0, 3.0, 2.8, 3.5, 3.3, 3.8, 3.5, 4.2, 3.9, 4.5, 4.2, 4.8),
        ("Octa-B: TP 5.0R (L7@4.6->4.3)", 0.8, 1.5, 1.0, 2.4, 2.0, 3.0, 2.8, 3.5, 3.3, 3.8, 3.5, 4.2, 3.9, 4.6, 4.3, 5.0),
        ("Octa-C: TP 5.2R (L7@4.7->4.4)", 0.8, 1.5, 1.0, 2.4, 2.0, 3.0, 2.8, 3.5, 3.3, 3.8, 3.5, 4.2, 3.9, 4.7, 4.4, 5.2),
    ]

    for name, be, l1_t, l1_a, l2_t, l2_a, l3_t, l3_a, l4_t, l4_a, l5_t, l5_a, l6_t, l6_a, l7_t, l7_a, tp in octa_configs:
        res = run_simulation(comb, m5_gold, m5_times, m5_len,
                             be_trigger=be, lock1_trig=l1_t, lock1_amt=l1_a,
                             lock2_trig=l2_t, lock2_amt=l2_a, lock3_trig=l3_t, lock3_amt=l3_a,
                             lock4_trig=l4_t, lock4_amt=l4_a, lock5_trig=l5_t, lock5_amt=l5_a,
                             lock6_trig=l6_t, lock6_amt=l6_a, lock7_trig=l7_t, lock7_amt=l7_a,
                             tp_r=tp)
        print(f"{name:32s} | Trades: {res['trades']:4d} | W/BE/L: {res['wins']:3d}/{res['bes']:3d}/{res['losses']:2d} | WR: {res['wr']:4.1f}% | Net: ${res['pnl']:8.2f} | PF: {res['pf']:5.2f} | MaxDD: ${res['max_dd']:5.2f} | Mos: {res['pos_m']}/{res['tot_m']}", flush=True)

if __name__ == "__main__":
    main()
