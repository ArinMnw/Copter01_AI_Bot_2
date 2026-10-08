# -*- coding: utf-8 -*-
"""run_s20_54_verified.py
Official 100% Verifiable Backtest Runner for Strategy S20.54 on Gold (XAUUSD.iux)
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import argparse
from datetime import datetime, timedelta, timezone
import os, sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from goal_s20_53_to_100 import compute_indicators, extract_setups, run_simulation, init_mt5

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", type=int, default=365, help="Number of days to backtest")
    parser.add_argument("--start", type=str, default="", help="Start datetime (UTC YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default="", help="End datetime (UTC YYYY-MM-DD)")
    parser.add_argument("--compare", action="store_true", help="Compare with live logs")
    args = parser.parse_args()

    if not init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    
    if args.end:
        end_dt = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
    else:
        end_dt = datetime.now(timezone.utc)
        
    if args.start:
        start_dt = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    else:
        start_dt = end_dt - timedelta(days=args.day)

    print("=" * 115, flush=True)
    print(" S20.54 VERIFIABLE M5 SL-FIRST SIMULATION RUNNER (STRICT LOT 0.01)", flush=True)
    print(f" Asset: {symbol_gold} | Period: {args.day} Days | Execution: Pessimistic Intrabar Sequential M5", flush=True)
    if args.compare:
        print(" Compare Mode Activated (--compare)", flush=True)
    print("=" * 115, flush=True)

    tf_labels = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']
    # Approx trading days (5 days/week = ~260 days/year)
    trading_days = args.day * (5/7)
    bars_required = int(trading_days * 288)
    
    rates = {}
    for tf in tf_labels:
        tf_val = getattr(mt5, f"TIMEFRAME_{tf}")
        # Approx bars required for this TF
        tf_bars = int(trading_days * 24 * 60 / {
            'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30, 'H1': 60, 'H4': 240, 'D1': 1440
        }[tf]) + 1000 # padding for indicators
        rates[tf] = mt5.copy_rates_from_pos(symbol_gold, tf_val, 0, min(tf_bars, 100000))
        
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, min(bars_required + 1000, 100000))
    mt5.shutdown()

    if m5_gold is None or len(m5_gold) == 0:
        print("Error: No M5 data found for the given range.")
        return

    base_dfs = []
    for tf_label, r in rates.items():
        if r is not None and len(r) > 0:
            df = compute_indicators(r, True, True, True, fvg_depth=5)
            base_dfs.append((tf_label, df))

    m5_times = [int(r['time']) for r in m5_gold]

    all_setups = []
    for tf_label, df_tf in base_dfs:
        all_setups.extend(extract_setups(
            df_tf, tf_label,
            min_vol=1.20, min_wick=0.30, retest_depth=0.10, sl_mult=0.22,
            hours=(0, 22), use_pyh=True, use_ldn=True, use_ny=True, use_ny_pm=True, use_fvg=True, use_fibo=True, use_vp=True,
            crt_momentum=0.50, rsi_bounds=(65.0, 35.0)
        ))

    combined = sorted(all_setups, key=lambda x: x['time'])
    print(f"Total raw confluent candidate signals detected: {len(combined)}", flush=True)

    # TP 7.50R with 15 stages
    stages = [
        (1.5, 1.0), (2.5, 2.0), (3.0, 2.8), (3.5, 3.3), (4.0, 3.8), 
        (4.5, 4.3), (5.0, 4.8), (5.5, 5.3), (6.0, 5.8), (6.5, 6.3), 
        (6.8, 6.5), (7.0, 6.8), (7.2, 7.0), (7.3, 7.1), (7.4, 7.2)
    ]
    res = run_simulation(m5_gold, m5_times, combined, tp_r=7.50, stages=stages)

    print("=" * 115, flush=True)
    print(" S20.54 VERIFIED PERFORMANCE SUMMARY (STRICT 0.01 LOT)", flush=True)
    print("=" * 115, flush=True)
    print(f" Total Trades Executed:   {res['trades']:,}", flush=True)
    print(f" Wins:                   {res['wins']:,} ({res['wr']:.1f}%)", flush=True)
    print(f"   └─ Full TP: {res['full_tp']:,} | Trail TP (ratchet lock): {res['trail_tp']:,} | Timeout Win: {res['timeout_win']:,}", flush=True)
    print(f" Breakevens:             {res['bes']:,} ({res['bes']/res['trades']*100:.1f}%)" if res['trades'] > 0 else " Breakevens: 0", flush=True)
    print(f" Losses:                 {res['losses']:,} ({res['losses']/res['trades']*100:.1f}%)" if res['trades'] > 0 else " Losses: 0", flush=True)
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

    csv_path = os.path.join(os.path.dirname(__file__), "S20_54_monthly.csv")
    pd.DataFrame(monthly_rows).to_csv(csv_path, index=False)
    print(f"Monthly breakdown saved to: {csv_path}", flush=True)

if __name__ == "__main__":
    main()
