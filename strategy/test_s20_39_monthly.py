# -*- coding: utf-8 -*-
"""test_s20_39_monthly.py
Inspect monthly breakdown for S20.39 Hours (4, 22) TP 4.6R
"""
import MetaTrader5 as mt5
import pandas as pd
import bisect
from datetime import datetime, timedelta, timezone
import os, sys

sys.path.append(os.path.dirname(__file__))
from s20_39_research import init_mt5, compute_indicators, extract_setups, run_simulation

def main():
    if not init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

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

    s0 = extract_setups(df_h4, "H4", min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=(4, 22), use_pqh=True)
    s1 = extract_setups(df_h1, "H1", min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=(4, 22), use_pqh=True)
    s2 = extract_setups(df_m30, "M30", min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=(4, 22), use_pqh=True)
    s3 = extract_setups(df_m15, "M15", min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=(4, 22), use_pqh=True)
    comb = sorted(s0 + s1 + s2 + s3, key=lambda x: x['time'])

    res = run_simulation(comb, m5_gold, m5_times, m5_len,
                         be_trigger=0.8, lock1_trig=1.5, lock1_amt=1.0,
                         lock2_trig=2.4, lock2_amt=2.0, lock3_trig=3.0, lock3_amt=2.8,
                         lock4_trig=3.5, lock4_amt=3.3, lock5_trig=3.8, lock5_amt=3.5,
                         lock6_trig=4.2, lock6_amt=3.9, tp_r=4.6)

    t_df = pd.DataFrame(res['records'])
    m_grp = t_df.groupby('month')
    print(f"Total Net PnL: ${res['pnl']:,.2f} | PF: {res['pf']:.2f} | MaxDD: ${res['max_dd']:.2f} | WR: {res['wr']:.1f}%")
    print(f"{'Month':8s} | {'Trades':6s} | {'Wins':4s} | {'BEs':4s} | {'Losses':6s} | {'WinRate':7s} | {'Net PnL ($)':11s}")
    print("-" * 65)
    for m, grp in m_grp:
        m_t = len(grp)
        m_w = (grp['outcome'] == 'WIN').sum()
        m_b = (grp['outcome'] == 'BE').sum()
        m_l = (grp['outcome'] == 'LOSS').sum()
        m_wr = m_w / m_t * 100.0 if m_t > 0 else 0.0
        m_pnl = grp['pnl'].sum()
        print(f"{m:8s} | {m_t:6d} | {m_w:4d} | {m_b:4d} | {m_l:6d} | {m_wr:6.1f}% | ${m_pnl:10.2f}")

if __name__ == "__main__":
    main()
