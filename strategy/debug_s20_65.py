# -*- coding: utf-8 -*-
import sys, os
sys.path.append(os.path.dirname(__file__))
from goal_s20_53_to_100 import compute_indicators, extract_setups, run_simulation, init_mt5
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone

def main():
    if not init_mt5():
        print("MT5 Init Failed")
        return
    symbol_gold = "XAUUSD.iux"
    now = datetime.now(timezone.utc); start_dt = now - timedelta(days=365)
    rates = {tf: mt5.copy_rates_range(symbol_gold, getattr(mt5, f"TIMEFRAME_{tf}"), start_dt, now) for tf in ['H4','H3','H2','H1','M30','M20','M15','M12']}
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)
    mt5.shutdown()
    m5_times = [int(r['time']) for r in m5_gold]

    base_dfs = [(tf, compute_indicators(r, True, True, True, fvg_depth=5)) for tf, r in rates.items()]

    stages_18 = [
        (1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5),
        (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4),
        (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3),
        (6.7, 6.5), (6.85, 6.65), (7.0, 6.8)
    ]

    target = 29756.75
    print(f"Target to beat: ${target:,.2f}")

    for wick in [0.25, 0.24, 0.23, 0.22, 0.20]:
        for depth in [0.124, 0.125, 0.126]:
            for vsa in [1.17, 1.16, 1.15]:
                all_s = []
                for tf_l, df_tf in base_dfs:
                    all_s.extend(extract_setups(df_tf, tf_l, min_vol=vsa, min_wick=wick, retest_depth=depth, sl_mult=0.20, hours=(0, 22), use_pyh=True, use_ldn=True, use_ny=True, use_ny_pm=True, use_fvg=True, use_fibo=True, use_vp=True))
                comb = sorted(all_s, key=lambda x: x['time'])

                for tp in [7.10, 7.15, 7.20, 7.25]:
                    res = run_simulation(m5_gold, m5_times, comb, tp_r=tp, stages=stages_18)
                    if res['pnl'] > target:
                        print(f"MATCH: wick={wick} depth={depth} vsa={vsa} TP={tp} -> PnL: ${res['pnl']:,.2f} Trades: {res['trades']} WR: {res['wr']:.1f}% DD: ${res['max_dd']:.2f}")

if __name__ == "__main__":
    main()
