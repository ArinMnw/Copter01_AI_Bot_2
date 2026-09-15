# -*- coding: utf-8 -*-
"""run_strict_confluence.py — 100% Honest, Zero-Lookahead, Pessimistic SL-First Backtest:
Rules:
1. Strict 0.01 Lot single position (no partial lot splits).
2. Pessimistic Intrabar: SL is ALWAYS checked first (if low <= sl, stopped out immediately, NO TP awarded).
3. Fill-bar guard: No same-bar instant TP on fill bar.
4. Causal indicators: Indicators at index i use only [:i+1], swings shifted by 1.
5. Systematic multi-strategy synergy comparison to find what combination strictly beats S20.30!
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

import strategy20_31


def simulate_strict_pessimistic(rates, df, synergy_mode="sweep_smt_vwap", tp_r=2.0, tf_name="M30"):
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
        res = strategy20_31.evaluate_setup(df, i, synergy_mode=synergy_mode)
        if not res:
            i += 1
            continue

        sig = res["signal"]
        entry = res["entry"]
        sl = res["sl"]
        risk = res["risk"]

        tp = round(entry + (tp_r * risk), 2) if sig == "BUY" else round(entry - (tp_r * risk), 2)
        be_trig = round(entry + (0.80 * risk), 2) if sig == "BUY" else round(entry - (0.80 * risk), 2)

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

        # Check fill bar for immediate SL breach
        fill_bar = future[fill_idx]
        current_sl = sl
        be_active = False
        trade_pnl = 0.0
        bars_held = 0
        outcome = None

        if sig == "BUY":
            if fill_bar['low'] <= current_sl:
                outcome = "LOSS"
                trade_pnl = -abs(entry - current_sl) * point_val
        else:
            if fill_bar['high'] >= current_sl:
                outcome = "LOSS"
                trade_pnl = -abs(current_sl - entry) * point_val

        # If not stopped out on fill bar, step through subsequent bars
        if outcome is None:
            for bar in future[fill_idx + 1:]:
                bars_held += 1
                if sig == "BUY":
                    # STRICT RULE: SL FIRST!
                    if bar['low'] <= current_sl:
                        if be_active:
                            outcome = "BE"
                            trade_pnl = 0.0
                        else:
                            outcome = "LOSS"
                            trade_pnl = -abs(entry - current_sl) * point_val
                        break

                    # ONLY IF SL NOT TOUCHED, CHECK TP
                    if bar['high'] >= tp:
                        outcome = "WIN"
                        trade_pnl = abs(tp - entry) * point_val
                        break

                    # CHECK BE TRIGGER
                    if not be_active and bar['high'] >= be_trig:
                        be_active = True
                        current_sl = entry

                else:  # SELL
                    # STRICT RULE: SL FIRST!
                    if bar['high'] >= current_sl:
                        if be_active:
                            outcome = "BE"
                            trade_pnl = 0.0
                        else:
                            outcome = "LOSS"
                            trade_pnl = -abs(current_sl - entry) * point_val
                        break

                    # ONLY IF SL NOT TOUCHED, CHECK TP
                    if bar['low'] <= tp:
                        outcome = "WIN"
                        trade_pnl = abs(entry - tp) * point_val
                        break

                    # CHECK BE TRIGGER
                    if not be_active and bar['low'] <= be_trig:
                        be_active = True
                        current_sl = entry

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
            "time": str(entry_time),
            "timestamp": int(future[fill_idx]['time']),
            "month": month_key,
            "outcome": outcome,
            "pnl": trade_pnl,
            "bars_held": bars_held
        })

        i += (fill_idx + max(1, bars_held // 2))

    gross_win = sum(r['pnl'] for r in records if r['pnl'] > 0)
    gross_loss = abs(sum(r['pnl'] for r in records if r['pnl'] < 0))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (99.9 if gross_win > 0 else 0.0)

    if records:
        t_df = pd.DataFrame(records)
        m_grouped = t_df.groupby('month')['pnl'].sum()
        pos_months = (m_grouped > 0).sum()
        tot_months = len(m_grouped)
        m_pct = (pos_months / tot_months * 100.0) if tot_months > 0 else 0.0
    else:
        pos_months, tot_months, m_pct = 0, 0, 0.0

    wr = (wins / trades * 100.0) if trades > 0 else 0.0
    non_losing = ((wins + bes) / trades * 100.0) if trades > 0 else 0.0

    return {
        "mode": synergy_mode,
        "tf": tf_name,
        "tp_r": tp_r,
        "trades": trades,
        "wins": wins,
        "bes": bes,
        "losses": losses,
        "wr": wr,
        "non_losing": non_losing,
        "net_pnl": pnl,
        "pf": pf,
        "max_dd": max_dd,
        "pos_months": pos_months,
        "tot_months": tot_months,
        "month_wr_pct": m_pct,
        "records": records
    }


def main():
    if not strategy20_31.parent_dir:
        return

    # Init MT5
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
        print("MT5 Init Error")
        return

    symbol_gold = "XAUUSD.iux"
    symbol_silver = "XAGUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    m30_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M30, start_dt, now)
    m30_silver = mt5.copy_rates_range(symbol_silver, mt5.TIMEFRAME_M30, start_dt, now)

    m15_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M15, start_dt, now)
    m15_silver = mt5.copy_rates_range(symbol_silver, mt5.TIMEFRAME_M15, start_dt, now)

    mt5.shutdown()

    m30_df = strategy20_31.compute_indicators_df(m30_gold, m30_silver)
    m15_df = strategy20_31.compute_indicators_df(m15_gold, m15_silver)

    print(f"\n{'='*95}")
    print(f" ZERO-LOOKAHEAD | STRICT LOT 0.01 | SL-FIRST PESSIMISTIC CONFLUENCE BENCHMARK")
    print(f"{'='*95}")

    combos = ["sweep_only", "sweep_smt", "sweep_smt_vwap"]

    for tf_name, g_rates, g_df in [("M30", m30_gold, m30_df), ("M15", m15_gold, m15_df)]:
        print(f"\n--- TIMEFRAME: {tf_name} ---")
        for c in combos:
            for rr in [1.8, 2.0, 2.2]:
                res = simulate_strict_pessimistic(g_rates, g_df, synergy_mode=c, tp_r=rr, tf_name=tf_name)
                print(f"Mode: {c:16s} | RR: {rr:.1f}R | Trades: {res['trades']:3d} | WR: {res['wr']:4.1f}% | NonLoss: {res['non_losing']:4.1f}% | Wins: {res['wins']:2d} | BE: {res['bes']:2d} | Loss: {res['losses']:2d} | PnL: ${res['net_pnl']:7.2f} | PF: {res['pf']:5.2f} | DD: ${res['max_dd']:5.2f} | WinMonths: {res['pos_months']}/{res['tot_months']}")


if __name__ == "__main__":
    main()
