# -*- coding: utf-8 -*-
import sys, os
sys.path.append(os.path.dirname(__file__))
from s20_51_research import compute_indicators, extract_setups, run_simulation, init_mt5
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
    base_dfs = [(tf, compute_indicators(r, True, True, True)) for tf, r in rates.items()]
    m5_times = [int(r['time']) for r in m5_gold]

    for wick in [0.32, 0.33]:
        all_s = []
        for tf_l, df_tf in base_dfs:
            all_s.extend(extract_setups(df_tf, tf_l, min_vol=1.17, min_wick=wick, retest_depth=0.124, hours=(0, 22), use_pyh=True, use_ldn=True, use_ny=True, use_ny_pm=True, use_fvg=True, use_fibo=True))
        comb = sorted(all_s, key=lambda x: x['time'])

        for tp in [6.70, 6.75, 6.80, 6.85, 6.90]:
            for l15 in [(6.50, 6.30), (6.55, 6.35)]:
                res = run_simulation(m5_gold, m5_times, comb, tp_r=tp, lock14_trig=6.35, lock14_amt=6.15, lock15_trig=l15[0], lock15_amt=l15[1])
                print(f"wick={wick} TP={tp} L15={l15} -> Trades: {res['trades']} WR: {res['wr']:.1f}% PnL: ${res['pnl']:,.2f} DD: ${res['max_dd']:.2f} Pos: {res['pos_months']}")

if __name__ == "__main__":
    main()
