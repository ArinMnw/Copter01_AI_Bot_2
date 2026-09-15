# -*- coding: utf-8 -*-
"""monthly_breakdown.py
Generates full monthly breakdown CSV and terminal table for S20.37 on Gold (XAUUSD.iux).
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import bisect
from datetime import datetime, timedelta, timezone
import os, sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

sys.path.append(os.path.dirname(__file__))
from strategy20_37 import compute_indicators, extract_setups

def init_mt5():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()

def main():
    if not init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    h4_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H4, start_dt, now)
    h1_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H1, start_dt, now)
    m30_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M30, start_dt, now)
    m15_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M15, start_dt, now)
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)
    mt5.shutdown()

    df_h4 = compute_indicators(h4_gold)
    df_h1 = compute_indicators(h1_gold)
    df_m30 = compute_indicators(m30_gold)
    df_m15 = compute_indicators(m15_gold)

    m5_times = [int(r['time']) for r in m5_gold]
    m5_len = len(m5_gold)

    s0 = extract_setups(df_h4, "H4", min_vol=1.20, retest_depth=0.150, hours=(7, 21))
    s1 = extract_setups(df_h1, "H1", min_vol=1.20, retest_depth=0.150, hours=(7, 21))
    s2 = extract_setups(df_m30, "M30", min_vol=1.20, retest_depth=0.150, hours=(7, 21))
    s3 = extract_setups(df_m15, "M15", min_vol=1.20, retest_depth=0.150, hours=(7, 21))
    all_setups = sorted(s0 + s1 + s2 + s3, key=lambda x: x['time'])

    be_trigger = 0.8
    lock1_trig = 1.5
    lock1_amt = 1.0
    lock2_trig = 2.4
    lock2_amt = 2.0
    lock3_trig = 3.0
    lock3_amt = 2.8
    lock4_trig = 3.5
    lock4_amt = 3.3
    tp_r = 4.0
    dedup_sec = 900

    lot = 0.01
    contract_size = 100.0
    point_val = contract_size * lot

    trades = 0
    records = []
    last_exit_time = 0

    for s in all_setups:
        sig_time = s["time"]
        if sig_time < last_exit_time + dedup_sec:
            continue

        m5_start = bisect.bisect_right(m5_times, sig_time)
        if m5_start >= m5_len:
            continue

        sig = s["signal"]
        entry = s["entry"]
        sl = s["sl"]
        risk = s["risk"]

        tp = round(entry + (tp_r * risk), 2) if sig == "BUY" else round(entry - (tp_r * risk), 2)
        be_price = round(entry + (be_trigger * risk), 2) if sig == "BUY" else round(entry - (be_trigger * risk), 2)

        l1_target = round(entry + (lock1_trig * risk), 2) if sig == "BUY" else round(entry - (lock1_trig * risk), 2)
        l1_sl = round(entry + (lock1_amt * risk), 2) if sig == "BUY" else round(entry - (lock1_amt * risk), 2)

        l2_target = round(entry + (lock2_trig * risk), 2) if sig == "BUY" else round(entry - (lock2_trig * risk), 2)
        l2_sl = round(entry + (lock2_amt * risk), 2) if sig == "BUY" else round(entry - (lock2_amt * risk), 2)

        l3_target = round(entry + (lock3_trig * risk), 2) if sig == "BUY" else round(entry - (lock3_trig * risk), 2)
        l3_sl = round(entry + (lock3_amt * risk), 2) if sig == "BUY" else round(entry - (lock3_amt * risk), 2)

        l4_target = round(entry + (lock4_trig * risk), 2) if sig == "BUY" else round(entry - (lock4_trig * risk), 2)
        l4_sl = round(entry + (lock4_amt * risk), 2) if sig == "BUY" else round(entry - (lock4_amt * risk), 2)

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
        l1_active = False
        l2_active = False
        l3_active = False
        l4_active = False
        trade_pnl = 0.0
        outcome = None
        exit_time = entry_time

        for k in range(fill_m5 + 1, min(fill_m5 + 288, m5_len)):
            b = m5_gold[k]
            exit_time = b['time']

            if sig == "BUY":
                if b['low'] <= current_sl:
                    if l4_active:
                        outcome = "WIN"
                        trade_pnl = (l4_sl - entry) * point_val
                    elif l3_active:
                        outcome = "WIN"
                        trade_pnl = (l3_sl - entry) * point_val
                    elif l2_active:
                        outcome = "WIN"
                        trade_pnl = (l2_sl - entry) * point_val
                    elif l1_active:
                        outcome = "WIN"
                        trade_pnl = (l1_sl - entry) * point_val
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

                if not l4_active and b['high'] >= l4_target:
                    l4_active = True
                    current_sl = l4_sl
                elif not l3_active and b['high'] >= l3_target:
                    l3_active = True
                    current_sl = l3_sl
                elif not l2_active and b['high'] >= l2_target:
                    l2_active = True
                    current_sl = l2_sl
                elif not l1_active and b['high'] >= l1_target:
                    l1_active = True
                    current_sl = l1_sl
                elif not be_active and b['high'] >= be_price:
                    be_active = True
                    current_sl = entry

            else: # SELL
                if b['high'] >= current_sl:
                    if l4_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l4_sl) * point_val
                    elif l3_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l3_sl) * point_val
                    elif l2_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l2_sl) * point_val
                    elif l1_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l1_sl) * point_val
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

                if not l4_active and b['low'] <= l4_target:
                    l4_active = True
                    current_sl = l4_sl
                elif not l3_active and b['low'] <= l3_target:
                    l3_active = True
                    current_sl = l3_sl
                elif not l2_active and b['low'] <= l2_target:
                    l2_active = True
                    current_sl = l2_sl
                elif not l1_active and b['low'] <= l1_target:
                    l1_active = True
                    current_sl = l1_sl
                elif not be_active and b['low'] <= be_price:
                    be_active = True
                    current_sl = entry

        if outcome is None:
            last_b = m5_gold[min(fill_m5 + 288, m5_len - 1)]
            close_p = last_b['close']
            trade_pnl = (close_p - entry) * point_val if sig == "BUY" else (entry - close_p) * point_val
            outcome = "WIN" if trade_pnl > 0.05 else ("LOSS" if trade_pnl < -0.05 else "BE")

        last_exit_time = exit_time
        records.append({"month": month_key, "outcome": outcome, "pnl": round(trade_pnl, 2)})

    t_df = pd.DataFrame(records)
    m_grp = t_df.groupby('month')
    monthly_rows = []
    for m, grp in m_grp:
        m_t = len(grp)
        m_w = (grp['outcome'] == 'WIN').sum()
        m_b = (grp['outcome'] == 'BE').sum()
        m_l = (grp['outcome'] == 'LOSS').sum()
        m_wr = m_w / m_t * 100.0 if m_t > 0 else 0.0
        m_pnl = grp['pnl'].sum()
        monthly_rows.append({"month": m, "trades": m_t, "wins": m_w, "bes": m_b, "losses": m_l, "win_rate": round(m_wr, 1), "pnl": round(m_pnl, 2)})

    out_csv = os.path.join(os.path.dirname(__file__), "S20_37_monthly.csv")
    pd.DataFrame(monthly_rows).to_csv(out_csv, index=False)
    print(f"Monthly breakdown generated successfully: {out_csv}")

if __name__ == "__main__":
    main()
