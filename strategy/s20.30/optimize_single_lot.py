# -*- coding: utf-8 -*-
"""optimize_single_lot.py — Optimize trade exit mechanics for strict Lot 0.01:
On a single 0.01 lot order, we cannot partially close.
We evaluate:
1. Target 2.2R with BE at 0.8R
2. Target 2.8R with BE at 1.0R
3. Target 3.5R with BE at 1.2R
4. Two-stage Trailing: At 1.8R lock +1.0R, at 2.8R lock +2.0R, Target 4.5R
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


def run_single_lot_optimization(rates, df, tf_name="M30"):
    lot = 0.01
    contract_size = 100.0
    point_val = contract_size * lot

    # Let's test different exit rules for strict 0.01 lot
    exit_rules = [
        ("TP_2.0R_BE_0.8R", 2.0, 0.40, 0.0),
        ("TP_2.5R_BE_1.0R", 2.5, 0.40, 0.0),
        ("TP_3.0R_BE_1.2R", 3.0, 0.40, 0.0),
        ("TwoStage_Lock1.2R_TP4.0R", 4.0, 0.40, 1.2),  # at 1.8R lock +1.2R, aim 4.0R
        ("TwoStage_Lock1.5R_TP4.5R", 4.5, 0.40, 1.5),  # at 2.0R lock +1.5R, aim 4.5R
    ]

    print(f"\n{'='*80}")
    print(f" OPTIMIZING SINGLE LOT 0.01 EXITS ({tf_name}) ON GRAND CONFLUENCE")
    print(f"{'='*80}")

    for name, final_tp_r, be_pct, lock_r in exit_rules:
        trades = 0
        wins = 0
        losses = 0
        bes = 0
        pnl = 0.0
        max_pnl = 0.0
        max_dd = 0.0
        trade_records = []

        i = 45
        n = len(rates)

        while i < n - 5:
            res = strategy20_30.evaluate_s20_30_bar(df, i, combo="combo_grand_synergy")
            if not res:
                i += 1
                continue

            sig = res["signal"]
            entry = res["entry"]
            sl = res["sl"]
            risk = res["risk"]

            final_tp = entry + (final_tp_r * risk) if sig == "BUY" else entry - (final_tp_r * risk)
            be_trig = entry + (final_tp_r * risk * be_pct) if sig == "BUY" else entry - (final_tp_r * risk * be_pct)
            lock_trig = entry + (1.8 * risk) if sig == "BUY" else entry - (1.8 * risk)

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
            active = future[fill_idx:]
            current_sl = sl
            be_active = False
            locked_active = False
            trade_pnl = 0.0
            bars_held = 0
            outcome = None

            for bar in active:
                bars_held += 1
                if sig == "BUY":
                    if not be_active and bar['high'] >= be_trig:
                        be_active = True
                        current_sl = entry

                    if lock_r > 0 and not locked_active and bar['high'] >= lock_trig:
                        locked_active = True
                        current_sl = entry + (lock_r * risk)

                    if bar['high'] >= final_tp:
                        trade_pnl = abs(final_tp - entry) * point_val
                        outcome = "FULL_WIN"
                        break

                    if bar['low'] <= current_sl:
                        if locked_active:
                            outcome = "LOCK_WIN"
                            trade_pnl = (current_sl - entry) * point_val
                        elif be_active:
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

                    if lock_r > 0 and not locked_active and bar['low'] <= lock_trig:
                        locked_active = True
                        current_sl = entry - (lock_r * risk)

                    if bar['low'] <= final_tp:
                        trade_pnl = abs(entry - final_tp) * point_val
                        outcome = "FULL_WIN"
                        break

                    if bar['high'] >= current_sl:
                        if locked_active:
                            outcome = "LOCK_WIN"
                            trade_pnl = (entry - current_sl) * point_val
                        elif be_active:
                            outcome = "BE"
                            trade_pnl = 0.0
                        else:
                            outcome = "LOSS"
                            trade_pnl = -abs(current_sl - entry) * point_val
                        break

            if outcome in ("FULL_WIN", "LOCK_WIN"):
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

            i += (fill_idx + max(1, bars_held // 2))

        wr = (wins / trades * 100.0) if trades > 0 else 0.0
        print(f"{name:30s} | Trades: {trades:3d} | WR: {wr:5.1f}% | Wins: {wins:3d} | BEs: {bes:3d} | Losses: {losses:2d} | NetPnL: ${pnl:8.2f} | MaxDD: ${max_dd:5.2f}")


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

    run_single_lot_optimization(g_m30, df_m30, tf_name="M30")
    run_single_lot_optimization(g_m15, df_m15, tf_name="M15")


if __name__ == "__main__":
    main()
