# -*- coding: utf-8 -*-
"""test_s20_51_fibo.py
Fine-tune Strategy 11 Fibonacci Premium/Discount Equilibrium Confluence with Quindeca Ratchet Locks.
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import bisect
from datetime import datetime, timedelta, timezone
import os, sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

sys.path.append(os.path.dirname(__file__))
from s20_51_research import compute_indicators, extract_setups, run_simulation, init_mt5

def main():
    if not init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    print("Fetching rates...")
    h4_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H4, start_dt, now)
    h3_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H3, start_dt, now)
    h2_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H2, start_dt, now)
    h1_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H1, start_dt, now)
    m30_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M30, start_dt, now)
    m20_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M20, start_dt, now)
    m15_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M15, start_dt, now)
    m12_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M12, start_dt, now)
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)
    mt5.shutdown()

    df_h4 = compute_indicators(h4_gold, use_london=True, use_ny=True, use_ny_pm=True)
    df_h3 = compute_indicators(h3_gold, use_london=True, use_ny=True, use_ny_pm=True)
    df_h2 = compute_indicators(h2_gold, use_london=True, use_ny=True, use_ny_pm=True)
    df_h1 = compute_indicators(h1_gold, use_london=True, use_ny=True, use_ny_pm=True)
    df_m30 = compute_indicators(m30_gold, use_london=True, use_ny=True, use_ny_pm=True)
    df_m20 = compute_indicators(m20_gold, use_london=True, use_ny=True, use_ny_pm=True)
    df_m15 = compute_indicators(m15_gold, use_london=True, use_ny=True, use_ny_pm=True)
    df_m12 = compute_indicators(m12_gold, use_london=True, use_ny=True, use_ny_pm=True)

    m5_times = [int(r['time']) for r in m5_gold]

    base_dfs = [
        ("H4", df_h4), ("H3", df_h3), ("H2", df_h2), ("H1", df_h1),
        ("M30", df_m30), ("M20", df_m20), ("M15", df_m15), ("M12", df_m12)
    ]

    for wick in [0.32, 0.33]:
        for depth in [0.122, 0.124]:
            all_s = []
            for tf_l, df_tf in base_dfs:
                all_s.extend(extract_setups(df_tf, tf_l, min_vol=1.17, min_wick=wick, retest_depth=depth, hours=(0, 22), use_pyh=True, use_ldn=True, use_ny=True, use_ny_pm=True, use_fvg=True, use_fibo=True))
            comb = sorted(all_s, key=lambda x: x['time'])

            for tp in [6.65, 6.70, 6.75]:
                for l15 in [(None, None), (6.50, 6.30), (6.55, 6.35)]:
                    l15_t, l15_a = l15
                    if l15_t is not None and tp <= l15_t:
                        continue
                    res = run_simulation(m5_gold, m5_times, comb, tp_r=tp, lock14_trig=6.35, lock14_amt=6.15, lock15_trig=l15_t, lock15_amt=l15_a)
                    print(f"wick={wick} depth={depth} TP={tp} L15={l15_t}->{l15_a} | Trades: {res['trades']} | WR: {res['wr']:.1f}% | PnL: ${res['pnl']:,.2f} | DD: ${res['max_dd']:.2f}")

if __name__ == "__main__":
    main()
