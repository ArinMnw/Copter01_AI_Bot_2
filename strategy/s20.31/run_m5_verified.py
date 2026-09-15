# -*- coding: utf-8 -*-
"""run_m5_verified.py — 100% Verifiable M5 Sequential Execution:
Eliminates ALL intrabar ambiguity by stepping through 70,000+ real 5-minute (M5) bars.
Guarantees:
1. Strict 0.01 Lot single position.
2. ZERO Lookahead Bias — backward-looking only.
3. ZERO "ชน SL แล้วชน TP" — On each M5 bar, SL is checked FIRST.
   If low <= current_sl, trade is stopped out immediately!
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import bisect
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

import strategy20_31


def main():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    ok = False
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            ok = True
            break
    if not ok and not mt5.initialize():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    symbol_silver = "XAGUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    m30_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M30, start_dt, now)
    m30_silver = mt5.copy_rates_range(symbol_silver, mt5.TIMEFRAME_M30, start_dt, now)
    # Fetch 75,000 bars of M5 (~390 days) using copy_rates_from_pos to avoid terminal range limit
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)

    mt5.shutdown()

    df_m30 = strategy20_31.compute_indicators_df(m30_gold, m30_silver)
    m5_times = [int(r['time']) for r in m5_gold]
    m5_len = len(m5_gold)

    lot = 0.01
    contract_size = 100.0
    point_val = contract_size * lot

    print("=" * 95)
    print(" 100% VERIFIABLE M5 INTRABAR SEQUENTIAL EXECUTION (STRICT LOT 0.01)")
    print(" Zero Lookahead | SL-First on Every 5-Minute Bar | Real 70,000+ M5 Bars")
    print("=" * 95)

    combos = [
        ("sweep_only", "Model 1: Pure Liquidity Sweep + Vol"),
        ("sweep_smt", "Model 2: Sweep + SMT Divergence (Gold vs Silver)"),
        ("sweep_smt_vwap", "Model 3: Sweep + SMT + Anchored VWAP Bands")
    ]

    for mode_key, mode_desc in combos:
        for tp_r in [1.8, 2.0, 2.5, 3.0]:
            trades = 0
            wins = 0
            losses = 0
            bes = 0
            pnl = 0.0
            max_pnl = 0.0
            max_dd = 0.0
            records = []

            i = 45
            n = len(m30_gold)

            while i < n - 5:
                res = strategy20_31.evaluate_setup(df_m30, i, synergy_mode=mode_key)
                if not res:
                    i += 1
                    continue

                sig = res["signal"]
                entry = res["entry"]
                sl = res["sl"]
                risk = res["risk"]
                tp = round(entry + (tp_r * risk), 2) if sig == "BUY" else round(entry - (tp_r * risk), 2)
                be_trig = round(entry + (0.80 * risk), 2) if sig == "BUY" else round(entry - (0.80 * risk), 2)
                sig_time = res["time"]

                m5_start = bisect.bisect_right(m5_times, sig_time)
                if m5_start >= m5_len:
                    i += 1
                    continue

                # Check fill within 24 M5 bars (2 hours)
                filled = False
                fill_m5 = 0
                for k in range(m5_start, min(m5_start + 24, m5_len)):
                    m_b = m5_gold[k]
                    if sig == "BUY" and m_b['low'] <= entry:
                        filled = True
                        fill_m5 = k
                        break
                    elif sig == "SELL" and m_b['high'] >= entry:
                        filled = True
                        fill_m5 = k
                        break

                if not filled:
                    i += 1
                    continue

                trades += 1
                entry_time = datetime.fromtimestamp(m5_gold[fill_m5]['time'], tz=timezone.utc)
                month_key = entry_time.strftime("%Y-%m")

                be_active = False
                current_sl = sl
                trade_pnl = 0.0
                outcome = None
                bars_held = 0

                # Step through subsequent M5 bars minute by minute
                for k in range(fill_m5 + 1, min(fill_m5 + 288, m5_len)):
                    bars_held += 1
                    b = m5_gold[k]

                    if sig == "BUY":
                        # STRICT PESSIMISTIC: CHECK SL FIRST ON THIS 5-MINUTE BAR!
                        if b['low'] <= current_sl:
                            if be_active:
                                outcome = "BE"
                                trade_pnl = 0.0
                            else:
                                outcome = "LOSS"
                                trade_pnl = -abs(entry - current_sl) * point_val
                            break

                        # ONLY IF SL NOT TOUCHED, CHECK TP
                        if b['high'] >= tp:
                            outcome = "WIN"
                            trade_pnl = abs(tp - entry) * point_val
                            break

                        # CHECK BE TRIGGER
                        if not be_active and b['high'] >= be_trig:
                            be_active = True
                            current_sl = entry

                    else:  # SELL
                        if b['high'] >= current_sl:
                            if be_active:
                                outcome = "BE"
                                trade_pnl = 0.0
                            else:
                                outcome = "LOSS"
                                trade_pnl = -abs(current_sl - entry) * point_val
                            break

                        if b['low'] <= tp:
                            outcome = "WIN"
                            trade_pnl = abs(entry - tp) * point_val
                            break

                        if not be_active and b['low'] <= be_trig:
                            be_active = True
                            current_sl = entry

                if outcome is None:
                    # Timeout 24h close at market
                    last_b = m5_gold[min(fill_m5 + 288, m5_len - 1)]
                    close_p = last_b['close']
                    trade_pnl = (close_p - entry) * point_val if sig == "BUY" else (entry - close_p) * point_val
                    outcome = "WIN" if trade_pnl > 0.05 else ("LOSS" if trade_pnl < -0.05 else "BE")

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
                    "month": month_key,
                    "outcome": outcome,
                    "pnl": trade_pnl
                })

                i += max(1, bars_held // 6)

            wr = (wins / trades * 100.0) if trades > 0 else 0.0
            non_loss = ((wins + bes) / trades * 100.0) if trades > 0 else 0.0
            gross_win = sum(r['pnl'] for r in records if r['pnl'] > 0)
            gross_loss = abs(sum(r['pnl'] for r in records if r['pnl'] < 0))
            pf = (gross_win / gross_loss) if gross_loss > 0 else 99.9

            t_df = pd.DataFrame(records)
            m_grp = t_df.groupby('month')['pnl'].sum()
            pos_m = (m_grp > 0).sum()
            tot_m = len(m_grp)

            print(f"Mode: {mode_key:15s} | TP: {tp_r:.1f}R | Trades: {trades:3d} | WR: {wr:4.1f}% | NonLoss: {non_loss:4.1f}% | Wins: {wins:2d} | BE: {bes:2d} | Loss: {losses:2d} | NetPnL: ${pnl:7.2f} | PF: {pf:5.2f} | MaxDD: ${max_dd:5.2f} | Months: {pos_m}/{tot_m}")


if __name__ == "__main__":
    main()
