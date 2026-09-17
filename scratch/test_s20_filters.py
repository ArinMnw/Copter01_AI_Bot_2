# -*- coding: utf-8 -*-
"""test_s20_filters.py
Adding High-Edge Filters to S20:
1. Session Filter: London & New York Active Hours only (07:00 - 19:00 UTC)
2. Trend / Bias Filter: Align with H1/H4 EMA / Daily Open Bias
3. FVG / Liquidity Sweep Confluence
"""
import sys, os, bisect
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

root_dir = r"d:\Project\Copter01_AI_Bot_2"
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, "strategy"))
sys.path.append(os.path.join(root_dir, "strategy", "s20.304"))

from goal_s20_53_to_100 import init_mt5
from run_master_s20_marathon_201_to_300 import compute_marathon_300_synergies
from test_rebuild_s20_304 import extract_rebuilt_setups
from test_s20_exit_engines import run_exit_engine_sim, summarize_df

def main():
    if not init_mt5():
        print("MT5 init failed")
        return
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=30)
    
    sym = "XAUUSDm"
    all_syms = [s.name for s in mt5.symbols_get()]
    if sym not in all_syms:
        sym = "XAUUSD.iux" if "XAUUSD.iux" in all_syms else all_syms[0]
        
    r_gold = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, start_dt, now)
    mt5.shutdown()
    
    df_m5 = compute_marathon_300_synergies(r_gold)
    m5_times = [int(r['time']) for r in r_gold]
    
    raw_setups = extract_rebuilt_setups(sym, {"M5": df_m5}, 2, 0.01, min_sl_usd=2.0)
    
    # Let's test filter combinations:
    print("\n" + "="*95)
    print(" 🛡️ AUDITING S20 WITH PROFESSIONAL QUANT FILTERS (XAUUSDm 30-Day Exness)")
    print("="*95)
    
    # 1. Base (Clean Fixed 1:3, BE @ 1R)
    t_base = run_exit_engine_sim(sym, r_gold, m5_times, raw_setups, target_rr=3.0, be_r=1.0)
    print(summarize_df("Base (No Filter, Fixed 1:3)", t_base))
    
    # 2. Session Filter (London 07-16 UTC, NY 12-20 UTC)
    session_setups = []
    for s in raw_setups:
        dt = datetime.fromtimestamp(s['time'], tz=timezone.utc)
        if 7 <= dt.hour <= 19:
            session_setups.append(s)
    t_sess = run_exit_engine_sim(sym, r_gold, m5_times, session_setups, target_rr=3.0, be_r=1.0)
    print(summarize_df("Session Filter (07:00 - 19:00 UTC)", t_sess))
    
    # 3. Session + Trend Bias Filter
    # In df_m5, we have 'daily_bias' (1 = Bull, -1 = Bear)
    time_to_row = {int(r['time']) + 300: r for r in df_m5.to_dict('records')}
    trend_setups = []
    for s in session_setups:
        row = time_to_row.get(s['time'])
        if row is not None:
            bias = row.get('daily_bias', 0)
            if s['signal'] == 'BUY' and bias >= 0:
                trend_setups.append(s)
            elif s['signal'] == 'SELL' and bias <= 0:
                trend_setups.append(s)
                
    t_trend = run_exit_engine_sim(sym, r_gold, m5_times, trend_setups, target_rr=3.0, be_r=1.0)
    print(summarize_df("Session + Daily Bias Trend Filter", t_trend))
    
    # 4. Session + Trend Bias + Higher RR (1:3.5)
    t_rr = run_exit_engine_sim(sym, r_gold, m5_times, trend_setups, target_rr=3.5, be_r=1.0)
    print(summarize_df("Session + Trend + Fixed 1:3.5", t_rr))
    
    # 5. Session + Trend + Fixed 1:2.0
    t_rr2 = run_exit_engine_sim(sym, r_gold, m5_times, trend_setups, target_rr=2.0, be_r=1.0)
    print(summarize_df("Session + Trend + Fixed 1:2.0", t_rr2))
    
    print("="*95 + "\n")

if __name__ == "__main__":
    main()
