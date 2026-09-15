# -*- coding: utf-8 -*-
"""monthly_breakdown.py — Generate detailed monthly tear sheet for S20.32 Champion.
Strict 0.01 Lot, M5 sequential execution, SL-first on every bar.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import bisect
from datetime import datetime, timedelta, timezone
import os, sys

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if current_dir not in sys.path:
    sys.path.append(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

import strategy20_32

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
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    m30_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M30, start_dt, now)
    m15_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M15, start_dt, now)
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)
    mt5.shutdown()

    df_m30 = strategy20_32.compute_indicators_df(m30_gold)
    df_m15 = strategy20_32.compute_indicators_df(m15_gold)

    m5_times = [int(r['time']) for r in m5_gold]
    m5_len = len(m5_gold)

    setups_m30 = []
    for i in range(45, len(df_m30)):
        s = strategy20_32.evaluate_setup(df_m30, i, tf_label="M30")
        if s:
            setups_m30.append(s)

    setups_m15 = []
    for i in range(45, len(df_m15)):
        s = strategy20_32.evaluate_setup(df_m15, i, tf_label="M15")
        if s:
            setups_m15.append(s)

    combined_setups = sorted(setups_m30 + setups_m15, key=lambda x: x['time'])

    lot = 0.01
    contract_size = 100.0
    point_val = contract_size * lot

    tp_r = 2.5
    be_r = 0.8
    lock_trig = 1.6
    lock_amt = 1.0

    trades = 0
    wins = 0
    losses = 0
    bes = 0
    pnl = 0.0
    max_pnl = 0.0
    max_dd = 0.0
    records = []
    last_exit_time = 0

    for s in combined_setups:
        sig_time = s["time"]
        if sig_time < last_exit_time + 900:
            continue

        m5_start = bisect.bisect_right(m5_times, sig_time)
        if m5_start >= m5_len:
            continue

        sig = s["signal"]
        entry = s["entry"]
        sl = s["sl"]
        risk = s["risk"]

        tp = round(entry + (tp_r * risk), 2) if sig == "BUY" else round(entry - (tp_r * risk), 2)
        be_price = round(entry + (be_r * risk), 2) if sig == "BUY" else round(entry - (be_r * risk), 2)
        lock_target = round(entry + (lock_trig * risk), 2) if sig == "BUY" else round(entry - (lock_trig * risk), 2)
        locked_sl = round(entry + (lock_amt * risk), 2) if sig == "BUY" else round(entry - (lock_amt * risk), 2)

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
            continue

        trades += 1
        entry_time = m5_gold[fill_m5]['time']
        entry_dt = datetime.fromtimestamp(entry_time, tz=timezone.utc)
        month_key = entry_dt.strftime("%Y-%m")

        current_sl = sl
        be_active = False
        lock_active = False
        trade_pnl = 0.0
        outcome = None
        exit_time = entry_time

        for k in range(fill_m5 + 1, min(fill_m5 + 288, m5_len)):
            b = m5_gold[k]
            exit_time = b['time']

            if sig == "BUY":
                if b['low'] <= current_sl:
                    if lock_active:
                        outcome = "WIN"
                        trade_pnl = (locked_sl - entry) * point_val
                    elif be_active:
                        outcome = "BE"
                        trade_pnl = 0.0
                    else:
                        outcome = "LOSS"
                        trade_pnl = -abs(entry - current_sl) * point_val
                    break

                if b['high'] >= tp:
                    outcome = "WIN"
                    trade_pnl = abs(tp - entry) * point_val
                    break

                if not lock_active and b['high'] >= lock_target:
                    lock_active = True
                    current_sl = locked_sl
                elif not be_active and b['high'] >= be_price:
                    be_active = True
                    current_sl = entry

            else: # SELL
                if b['high'] >= current_sl:
                    if lock_active:
                        outcome = "WIN"
                        trade_pnl = (entry - locked_sl) * point_val
                    elif be_active:
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

                if not lock_active and b['low'] <= lock_target:
                    lock_active = True
                    current_sl = locked_sl
                elif not be_active and b['low'] <= be_price:
                    be_active = True
                    current_sl = entry

        if outcome is None:
            last_b = m5_gold[min(fill_m5 + 288, m5_len - 1)]
            close_p = last_b['close']
            trade_pnl = (close_p - entry) * point_val if sig == "BUY" else (entry - close_p) * point_val
            outcome = "WIN" if trade_pnl > 0.05 else ("LOSS" if trade_pnl < -0.05 else "BE")

        last_exit_time = exit_time

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

    t_df = pd.DataFrame(records)
    csv_path = os.path.join(current_dir, "S20_32_monthly.csv")
    
    monthly_stats = []
    print("\n" + "=" * 95)
    print(" S20.32 DUAL-HORIZON INSTITUTIONAL SYNERGY — 365-DAY MONTHLY TEAR SHEET")
    print(" (Strict 0.01 Lot | 100% Sequential M5 Execution | SL Checked First)")
    print("=" * 95)
    print(f"{'Month':^10} | {'Trades':^8} | {'Wins':^8} | {'BEs':^8} | {'Losses':^8} | {'Net PnL ($)':^14} | {'Win Rate':^10}")
    print("-" * 95)

    for m, grp in t_df.groupby('month'):
        m_trades = len(grp)
        m_wins = (grp['outcome'] == 'WIN').sum()
        m_bes = (grp['outcome'] == 'BE').sum()
        m_loss = (grp['outcome'] == 'LOSS').sum()
        m_pnl = grp['pnl'].sum()
        m_wr = (m_wins / m_trades * 100.0) if m_trades > 0 else 0.0

        monthly_stats.append({
            "month": m,
            "trades": m_trades,
            "wins": m_wins,
            "bes": m_bes,
            "losses": m_loss,
            "pnl": round(m_pnl, 2),
            "win_rate": round(m_wr, 1)
        })
        print(f"{m:^10} | {m_trades:^8d} | {m_wins:^8d} | {m_bes:^8d} | {m_loss:^8d} | {m_pnl:^14.2f} | {m_wr:^9.1f}%")

    print("-" * 95)
    tot_wr = (wins / trades * 100.0) if trades > 0 else 0.0
    print(f"{'TOTAL':^10} | {trades:^8d} | {wins:^8d} | {bes:^8d} | {losses:^8d} | {pnl:^14.2f} | {tot_wr:^9.1f}%")
    print("=" * 95)
    print(f"Profit Factor: {(sum(r['pnl'] for r in records if r['pnl'] > 0) / abs(sum(r['pnl'] for r in records if r['pnl'] < 0))):.2f}")
    print(f"Max Drawdown:  ${max_dd:.2f}")
    print(f"Avg Monthly:   ${(pnl / len(monthly_stats)):.2f} / month on strict 0.01 lot")

    pd.DataFrame(monthly_stats).to_csv(csv_path, index=False)
    print(f"Saved monthly CSV to: {csv_path}")

if __name__ == "__main__":
    main()
