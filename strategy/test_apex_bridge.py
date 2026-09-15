# -*- coding: utf-8 -*-
import sys
sys.path.append('strategy')
from goal_s20_53_to_100 import compute_indicators, extract_setups, run_simulation, init_mt5
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone

init_mt5()
rates = {tf: mt5.copy_rates_range('XAUUSD.iux', getattr(mt5, f'TIMEFRAME_{tf}'), datetime.now(timezone.utc)-timedelta(days=365), datetime.now(timezone.utc)) for tf in ['H4','H3','H2','H1','M30','M20','M15','M12']}
m5_gold = mt5.copy_rates_from_pos('XAUUSD.iux', mt5.TIMEFRAME_M5, 0, 75000)
mt5.shutdown()
m5_times = [int(r['time']) for r in m5_gold]
base_dfs = [(tf, compute_indicators(r, True, True, True, fvg_depth=5)) for tf, r in rates.items()]

stages = [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75), (9.1, 8.9), (9.25, 9.05), (9.4, 9.2)]

champion_pnl = 34635.07
for wick in [0.14, 0.13, 0.12]:
    for depth in [0.124, 0.125]:
        all_s = []
        for tf_label, df_tf in base_dfs:
            all_s.extend(extract_setups(df_tf, tf_label, min_vol=1.17, min_wick=wick, retest_depth=depth, hours=(0, 22), use_pyh=True, use_ldn=True, use_ny=True, use_ny_pm=True, use_fvg=True, use_fibo=True, use_vp=True))
        comb = sorted(all_s, key=lambda x: x['time'])
        for tp in [11.25, 11.35, 11.50, 11.60]:
            res = run_simulation(m5_gold, m5_times, comb, tp_r=tp, stages=stages)
            if res['pnl'] > champion_pnl:
                print(f"FOUND: wick={wick} depth={depth} tp={tp} -> PnL: ${res['pnl']:,.2f} Trades: {res['trades']} WR: {res['wr']:.1f}% DD: ${res['max_dd']:.2f}")
