# -*- coding: utf-8 -*-
"""check_h3_and_windows.py
Check H3 Horizon on Windows (3, 22) and (2, 22)
"""
import MetaTrader5 as mt5
import pandas as pd
import bisect
from datetime import datetime, timedelta, timezone
import os, sys

sys.path.append(os.path.dirname(__file__))
from s20_41_research import init_mt5, compute_indicators, extract_setups, run_simulation

def main():
    if not init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    h4_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H4, start_dt, now)
    h3_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H3, start_dt, now)
    h2_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H2, start_dt, now)
    h1_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H1, start_dt, now)
    m30_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M30, start_dt, now)
    m15_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M15, start_dt, now)
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)
    mt5.shutdown()

    df_h4 = compute_indicators(h4_gold)
    df_h3 = compute_indicators(h3_gold)
    df_h2 = compute_indicators(h2_gold)
    df_h1 = compute_indicators(h1_gold)
    df_m30 = compute_indicators(m30_gold)
    df_m15 = compute_indicators(m15_gold)

    m5_times = [int(r['time']) for r in m5_gold]
    m5_len = len(m5_gold)

    for win in [(3, 22), (2, 22)]:
        s0 = extract_setups(df_h4, "H4", min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=win, use_pyh=True)
        s_h3 = extract_setups(df_h3, "H3", min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=win, use_pyh=True)
        s_h2 = extract_setups(df_h2, "H2", min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=win, use_pyh=True)
        s1 = extract_setups(df_h1, "H1", min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=win, use_pyh=True)
        s2 = extract_setups(df_m30, "M30", min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=win, use_pyh=True)
        s3 = extract_setups(df_m15, "M15", min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=win, use_pyh=True)
        comb = sorted(s0 + s_h3 + s_h2 + s1 + s2 + s3, key=lambda x: x['time'])

        res = run_simulation(comb, m5_gold, m5_times, m5_len,
                             be_trigger=0.8, lock1_trig=1.5, lock1_amt=1.0,
                             lock2_trig=2.4, lock2_amt=2.0, lock3_trig=3.0, lock3_amt=2.8,
                             lock4_trig=3.5, lock4_amt=3.3, lock5_trig=3.8, lock5_amt=3.5,
                             lock6_trig=4.2, lock6_amt=3.9, lock7_trig=4.6, lock7_amt=4.3,
                             lock8_trig=0.0, lock8_amt=0.0, tp_r=5.0)
        print(f"Window {win}: Trades: {res['trades']:4d} | W/BE/L: {res['wins']:3d}/{res['bes']:3d}/{res['losses']:2d} | WR: {res['wr']:4.1f}% | Net: ${res['pnl']:8.2f} | PF: {res['pf']:5.2f} | MaxDD: ${res['max_dd']:5.2f} | Mos: {res['pos_m']}/{res['tot_m']}", flush=True)

if __name__ == "__main__":
    main()
