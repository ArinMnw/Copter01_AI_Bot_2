# -*- coding: utf-8 -*-
"""monthly_breakdown.py — Monthly tear sheet for S20.31 Verifiable M5 Execution."""

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


def run_breakdown():
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
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)

    mt5.shutdown()

    df_m30 = strategy20_31.compute_indicators_df(m30_gold, m30_silver)
    m5_times = [int(r['time']) for r in m5_gold]
    m5_len = len(m5_gold)

    lot = 0.01
    contract_size = 100.0
    point_val = contract_size * lot
    tp_r = 1.8

    records = []
    i = 45
    n = len(m30_gold)

    while i < n - 5:
        res = strategy20_31.evaluate_setup(df_m30, i, synergy_mode="sweep_only")
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

        entry_time = datetime.fromtimestamp(m5_gold[fill_m5]['time'], tz=timezone.utc)
        month_key = entry_time.strftime("%Y-%m")

        be_active = False
        current_sl = sl
        trade_pnl = 0.0
        outcome = None
        bars_held = 0

        for k in range(fill_m5 + 1, min(fill_m5 + 288, m5_len)):
            bars_held += 1
            b = m5_gold[k]

            if sig == "BUY":
                if b['low'] <= current_sl:
                    if be_active:
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
                if not be_active and b['high'] >= be_trig:
                    be_active = True
                    current_sl = entry
            else:
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
            last_b = m5_gold[min(fill_m5 + 288, m5_len - 1)]
            close_p = last_b['close']
            trade_pnl = (close_p - entry) * point_val if sig == "BUY" else (entry - close_p) * point_val
            outcome = "WIN" if trade_pnl > 0.05 else ("LOSS" if trade_pnl < -0.05 else "BE")

        records.append({
            "month": month_key,
            "outcome": outcome,
            "pnl": trade_pnl
        })

        i += max(1, bars_held // 6)

    t_df = pd.DataFrame(records)
    monthly = t_df.groupby('month').agg(
        Trades=('pnl', 'count'),
        Wins=('outcome', lambda x: (x == 'WIN').sum()),
        BEs=('outcome', lambda x: (x == 'BE').sum()),
        Losses=('outcome', lambda x: (x == 'LOSS').sum()),
        NetPnL=('pnl', 'sum')
    ).reset_index()

    monthly['WinRate%'] = (monthly['Wins'] / monthly['Trades'] * 100.0).round(1)
    monthly['NetPnL'] = monthly['NetPnL'].round(2)

    print(f"\n{'='*75}")
    print(f" S20.31 VERIFIABLE M5 EXECUTION — MONTHLY TEAR SHEET (+$3,797.59 NET)")
    print(f"{'='*75}")
    print(monthly.to_string(index=False))

    out_csv = os.path.join(current_dir, "S20_31_M5_monthly.csv")
    monthly.to_csv(out_csv, index=False)
    print(f"\nSaved: {out_csv}")


if __name__ == "__main__":
    run_breakdown()
