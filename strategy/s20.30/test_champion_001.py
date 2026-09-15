# -*- coding: utf-8 -*-
"""test_champion_001.py — Champion S20.30 Dual Horizon on STRICT Lot 0.01:
Tests the exact synergy that won:
Liquidity Sweep (Asia H/L + PDH/PDL + Swing 12) + SMT Intermarket Divergence
With Dual-Horizon (M15 + M30) at STRICT LOT 0.01.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if current_dir not in sys.path:
    sys.path.append(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

import strategy20_30
import backtest_s20_30_runner


def run_single(rates, df, tf_name="M15", tp_r=2.2):
    lot = 0.01
    contract_size = 100.0
    point_val = contract_size * lot

    trades = 0
    wins = 0
    losses = 0
    bes = 0
    pnl = 0.0
    max_pnl = 0.0
    max_dd = 0.0
    records = []

    i = 45
    n = len(rates)

    while i < n - 5:
        # Combo B: Sweep + SMT
        res = strategy20_30.evaluate_s20_30_bar(df, i, combo="combo_sweep_smt")
        if not res:
            i += 1
            continue

        sig = res["signal"]
        entry = res["entry"]
        sl = res["sl"]
        risk = res["risk"]

        tp = entry + (tp_r * risk) if sig == "BUY" else entry - (tp_r * risk)
        be_trig = entry + (0.8 * risk) if sig == "BUY" else entry - (0.8 * risk)

        future = rates[i + 1:]
        filled = False
        fill_idx = 0
        for f_idx, f_bar in enumerate(future[:5]):
            if sig == "BUY" and f_bar['low'] <= entry:
                filled = True
                fill_idx = f_idx
                break
            elif sig == "SELL" and f_bar['high'] >= entry:
                filled = True
                fill_idx = f_idx
                break

        if not filled:
            i += 1
            continue

        trades += 1
        entry_time = datetime.fromtimestamp(future[fill_idx]['time'], tz=timezone.utc)
        month_key = entry_time.strftime("%Y-%m")
        active = future[fill_idx:]

        be_active = False
        current_sl = sl
        trade_pnl = 0.0
        bars_held = 0
        outcome = None

        for bar in active:
            bars_held += 1
            if sig == "BUY":
                if not be_active and bar['high'] >= be_trig:
                    be_active = True
                    current_sl = entry

                if bar['high'] >= tp:
                    trade_pnl = abs(tp - entry) * point_val
                    outcome = "WIN"
                    break

                if bar['low'] <= current_sl:
                    if be_active:
                        outcome = "BE"
                        trade_pnl = 0.0
                    else:
                        outcome = "LOSS"
                        trade_pnl = -abs(entry - current_sl) * point_val
                    break

            else:  # SELL
                if not be_active and bar['low'] <= be_trig:
                    be_active = True
                    current_sl = entry

                if bar['low'] <= tp:
                    trade_pnl = abs(entry - tp) * point_val
                    outcome = "WIN"
                    break

                if bar['high'] >= current_sl:
                    if be_active:
                        outcome = "BE"
                        trade_pnl = 0.0
                    else:
                        outcome = "LOSS"
                        trade_pnl = -abs(current_sl - entry) * point_val
                    break

        if outcome == "WIN":
            wins += 1
        elif outcome == "LOSS":
            losses += 1
        else:
            bes += 1

        pnl += trade_pnl
        if pnl > max_pnl:
            max_pnl = pnl
        dd = max_pnl - pnl
        if dd > max_dd:
            max_dd = dd

        records.append({
            "timestamp": int(future[fill_idx]['time']),
            "time": str(entry_time),
            "month": month_key,
            "outcome": outcome,
            "pnl": trade_pnl
        })

        i += (fill_idx + max(1, bars_held // 2))

    return records, pnl, max_dd, wins, bes, losses, trades


def main():
    if not backtest_s20_30_runner.init_mt5():
        return

    symbol_gold = "XAUUSD.iux"
    symbol_silver = "XAGUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    g_m30 = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M30, start_dt, now)
    s_m30 = mt5.copy_rates_range(symbol_silver, mt5.TIMEFRAME_M30, start_dt, now)

    g_m15 = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M15, start_dt, now)
    s_m15 = mt5.copy_rates_range(symbol_silver, mt5.TIMEFRAME_M15, start_dt, now)

    mt5.shutdown()

    df_m30 = strategy20_30.compute_indicators_df(g_m30, s_m30)
    df_m15 = strategy20_30.compute_indicators_df(g_m15, s_m15)

    rec15, pnl15, dd15, w15, b15, l15, t15 = run_single(g_m15, df_m15, tf_name="M15", tp_r=2.2)
    rec30, pnl30, dd30, w30, b30, l30, t30 = run_single(g_m30, df_m30, tf_name="M30", tp_r=2.2)

    print(f"M15 Solo: Trades {t15} | Wins {w15} | BEs {b15} | Losses {l15} | NetPnL ${pnl15:.2f} | MaxDD ${dd15:.2f}")
    print(f"M30 Solo: Trades {t30} | Wins {w30} | BEs {b30} | Losses {l30} | NetPnL ${pnl30:.2f} | MaxDD ${dd30:.2f}")

    # Combine & Deduplicate
    combined = list(rec15)
    t15_times = [r['timestamp'] for r in rec15]
    for r30 in rec30:
        if not any(abs(r30['timestamp'] - t) <= 1800 for t in t15_times):
            combined.append(r30)

    combined.sort(key=lambda x: x['timestamp'])

    tot_pnl = sum(r['pnl'] for r in combined)
    max_pnl = 0.0
    tot_dd = 0.0
    cum = 0.0
    for r in combined:
        cum += r['pnl']
        if cum > max_pnl:
            max_pnl = cum
        if max_pnl - cum > tot_dd:
            tot_dd = max_pnl - cum

    w_tot = sum(1 for r in combined if r['outcome'] == 'WIN')
    b_tot = sum(1 for r in combined if r['outcome'] == 'BE')
    l_tot = sum(1 for r in combined if r['outcome'] == 'LOSS')
    n_tot = len(combined)

    print(f"\n{'='*75}")
    print(f" S20.30 DUAL-HORIZON (SWEEP + SMT) STRICT LOT 0.01 RESULT:")
    print(f"{'='*75}")
    print(f"Trades: {n_tot} | Wins: {w_tot} ({w_tot/n_tot*100:.1f}%) | BEs: {b_tot} | Losses: {l_tot} ({l_tot/n_tot*100:.1f}%)")
    print(f"Net Profit: ${tot_pnl:.2f} (Strict Lot 0.01!) | Max Drawdown: ${tot_dd:.2f}")

    # Monthly breakdown
    t_df = pd.DataFrame(combined)
    m_grp = t_df.groupby('month')['pnl'].sum().reset_index()
    print("\nMonthly PnL:")
    print(m_grp.to_string(index=False))


if __name__ == "__main__":
    main()
