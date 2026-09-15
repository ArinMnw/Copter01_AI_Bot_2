# -*- coding: utf-8 -*-
"""run_s20_126_m5_verified.py
Official 100% Verifiable Backtest Runner for Strategy S20.126 on Gold (XAUUSD.iux)
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import bisect
from datetime import datetime, timedelta, timezone
import os, sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from goal_s20_53_to_100 import compute_indicators, extract_setups, run_simulation, init_mt5

def main():
    if not init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    print("=" * 115, flush=True)
    print(" S20.126 VERIFIABLE M5 SL-FIRST SIMULATION RUNNER (STRICT LOT 0.01)", flush=True)
    print(f" Asset: {symbol_gold} | Period: 365 Days | Execution: Pessimistic Intrabar Sequential M5", flush=True)
    print("=" * 115, flush=True)

    rates = {tf: mt5.copy_rates_range(symbol_gold, getattr(mt5, f"TIMEFRAME_{tf}"), start_dt, now) for tf in ['H4','H3','H2','H1','M30','M20','M15','M12']}
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)
    mt5.shutdown()

    base_dfs = [(tf, compute_indicators(r, True, True, True, fvg_depth=5)) for tf, r in rates.items()]
    m5_times = [int(r['time']) for r in m5_gold]

    all_setups = []
    for tf_label, df_tf in base_dfs:
        all_setups.extend(extract_setups(
            df_tf, tf_label,
            min_vol=1.17, min_wick=0.14, retest_depth=0.124,
            hours=(0, 22), use_pyh=True, use_ldn=True, use_ny=True, use_ny_pm=True, use_fvg=True, use_fibo=True, use_vp=True
        ))

    combined = sorted(all_setups, key=lambda x: x['time'])
    print(f"Total raw confluent candidate signals detected: {len(combined)}", flush=True)

    stages = [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75)]
    res = run_simulation(m5_gold, m5_times, combined, tp_r=11.15, stages=stages)

    print("=" * 115, flush=True)
    print(" S20.126 VERIFIED PERFORMANCE SUMMARY (STRICT 0.01 LOT)", flush=True)
    print("=" * 115, flush=True)
    print(f" Total Trades Executed:   {res['trades']:,}", flush=True)
    print(f" Wins:                   {res['wins']:,} ({res['wr']:.1f}%)", flush=True)
    print(f" Breakevens:             {res['bes']:,} ({res['bes']/res['trades']*100:.1f}%)", flush=True)
    print(f" Losses:                 {res['losses']:,} ({res['losses']/res['trades']*100:.1f}%)", flush=True)
    print(f" Non-Loss Rate:          {res['non_loss_rate']:.1f}%", flush=True)
    print(f" Gross Profit:           ${res['gross_profit']:,.2f}", flush=True)
    print(f" Gross Loss:             ${res['gross_loss']:,.2f}", flush=True)
    print(f" Profit Factor:          {res['pf']:.2f}", flush=True)
    print(f" Net Profit:             ${res['pnl']:,.2f}", flush=True)
    print(f" Max Drawdown:           ${res['max_dd']:,.2f}", flush=True)
    print("=" * 115, flush=True)

    monthly_rows = []
    for m in sorted(res['monthly_stats'].keys()):
        st = res['monthly_stats'][m]
        m_wr = (st['wins'] / st['trades'] * 100) if st['trades'] > 0 else 0
        monthly_rows.append({
            "month": m,
            "trades": st['trades'],
            "wins": st['wins'],
            "bes": st['bes'],
            "losses": st['losses'],
            "win_rate": round(m_wr, 1),
            "pnl": round(st['pnl'], 2)
        })

    csv_path = os.path.join(os.path.dirname(__file__), "S20_126_monthly.csv")
    pd.DataFrame(monthly_rows).to_csv(csv_path, index=False)
    print(f"Monthly breakdown saved to: {csv_path}", flush=True)

if __name__ == "__main__":
    main()
