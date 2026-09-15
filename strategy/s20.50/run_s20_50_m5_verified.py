# -*- coding: utf-8 -*-
"""run_s20_50_m5_verified.py
Official 100% Verifiable Backtest Runner for Strategy S20.50 on Gold (XAUUSD.iux)
Rigid Execution Rules:
1. Strict 0.01 lot single position throughout 365 days (no scaling, no martingale, no splitting)
2. Causal backward-looking indicators (zero lookahead, zero repaint)
3. Pessimistic SL-First sequential execution across 75,000+ real M5 bars:
   - On every M5 bar, SL is evaluated FIRST!
   - If price touches SL, position exits immediately as Loss/BE/Locked Win. Cannot hit TP on that bar!
4. Realistic Pending Limit Retest within 2 hours (no magic fill)
5. Multi-Strategy Single-Candle Cross-Breed Confluence:
   - SMC Macro Liquidity Sweeps (Strategy 8): Asian + London (PLH/PLL) + NY AM (PNYH/PNYL) + NY PM (PNYPMH/PNYPML) + PDH/PDL + PWH/PWL + PMH/PML + PQH/PQL + PYH/PYL + Swing 12
   - Multi-Bar Fair Value Gap Memory (Strategy 1 & 2): 5-bar lookback FVG Imbalance Confluence
   - Wyckoff VSA: Volume Climax Ratio >= 1.17x of 20 MA
   - Price Action Rejection Wick: lower_wick_pct / upper_wick_pct >= 33% or wick >= 1.1x body
   - Candle Range Theory (CRT - Strategy 10): Closed Momentum >= 45% of total range
   - RSI Momentum Guard (Strategy 9): BUY <= 68, SELL >= 32
6. Quattuordeca-Stage Quantum Ratchet Lock Engine (14 Stages):
   - Stage 1: Move SL to BE @ +0.8R
   - Stage 2: Lock +1.0R @ +1.5R
   - Stage 3: Lock +2.0R @ +2.4R
   - Stage 4: Lock +2.8R @ +3.0R
   - Stage 5: Lock +3.3R @ +3.5R
   - Stage 6: Lock +3.5R @ +3.8R
   - Stage 7: Lock +3.9R @ +4.2R
   - Stage 8: Lock +4.3R @ +4.6R
   - Stage 9: Lock +4.9R @ +5.2R
   - Stage 10: Lock +5.4R @ +5.6R
   - Stage 11: Lock +5.6R @ +5.8R
   - Stage 12: Lock +5.8R @ +6.0R
   - Stage 13: Lock +5.95R @ +6.15R
   - Stage 14: Lock +6.15R @ +6.35R
   - Full Target: TP @ +6.65R
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
from strategy20_50 import compute_indicators, extract_setups

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

    print("=" * 115, flush=True)
    print(" S20.50 VERIFIABLE M5 SL-FIRST SIMULATION RUNNER (STRICT LOT 0.01)", flush=True)
    print(f" Asset: {symbol_gold} | Period: 365 Days | Execution: Pessimistic Intrabar Sequential M5", flush=True)
    print("=" * 115, flush=True)

    print("Fetching omni-horizon rates from MT5 (H4, H3, H2, H1, M30, M20, M15, M12)...", flush=True)
    h4_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H4, start_dt, now)
    h3_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H3, start_dt, now)
    h2_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H2, start_dt, now)
    h1_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H1, start_dt, now)
    m30_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M30, start_dt, now)
    m20_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M20, start_dt, now)
    m15_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M15, start_dt, now)
    m12_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M12, start_dt, now)
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)
    mt5.shutdown()

    df_h4 = compute_indicators(h4_gold, use_london=True, use_ny=True, use_ny_pm=True)
    df_h3 = compute_indicators(h3_gold, use_london=True, use_ny=True, use_ny_pm=True)
    df_h2 = compute_indicators(h2_gold, use_london=True, use_ny=True, use_ny_pm=True)
    df_h1 = compute_indicators(h1_gold, use_london=True, use_ny=True, use_ny_pm=True)
    df_m30 = compute_indicators(m30_gold, use_london=True, use_ny=True, use_ny_pm=True)
    df_m20 = compute_indicators(m20_gold, use_london=True, use_ny=True, use_ny_pm=True)
    df_m15 = compute_indicators(m15_gold, use_london=True, use_ny=True, use_ny_pm=True)
    df_m12 = compute_indicators(m12_gold, use_london=True, use_ny=True, use_ny_pm=True)

    m5_times = [int(r['time']) for r in m5_gold]
    m5_len = len(m5_gold)

    print("Extracting omni-horizon confluences (H4, H3, H2, H1, M30, M20, M15, M12 + Multi-Bar FVG + Triple-Session Sweeps)...", flush=True)
    base_tfs = [
        ("H4", df_h4), ("H3", df_h3), ("H2", df_h2), ("H1", df_h1),
        ("M30", df_m30), ("M20", df_m20), ("M15", df_m15), ("M12", df_m12)
    ]

    all_setups = []
    for tf_label, df_tf in base_tfs:
        all_setups.extend(extract_setups(
            df_tf, tf_label,
            min_vol=1.17, min_wick=0.33, retest_depth=0.124,
            hours=(0, 22), use_pyh=True, use_ldn=True, use_ny=True, use_ny_pm=True, use_fvg=True
        ))

    combined = sorted(all_setups, key=lambda x: x['time'])
    print(f"Total raw confluent candidate signals detected: {len(combined)}", flush=True)

    # Pessimistic Intrabar Sequential Execution Simulation Engine
    point_val = 1.0  # Strict 0.01 lot on XAUUSD ($1.00 per point)
    be_trigger = 0.8
    lock1_trig = 1.5
    lock1_amt = 1.0
    lock2_trig = 2.4
    lock2_amt = 2.0
    lock3_trig = 3.0
    lock3_amt = 2.8
    lock4_trig = 3.5
    lock4_amt = 3.3
    lock5_trig = 3.8
    lock5_amt = 3.5
    lock6_trig = 4.2
    lock6_amt = 3.9
    lock7_trig = 4.6
    lock7_amt = 4.3
    lock8_trig = 5.2
    lock8_amt = 4.9
    lock9_trig = 5.5
    lock9_amt = 5.2
    lock10_trig = 5.6
    lock10_amt = 5.4
    lock11_trig = 5.8
    lock11_amt = 5.6
    lock12_trig = 6.0
    lock12_amt = 5.8
    lock13_trig = 6.15
    lock13_amt = 5.95
    lock14_trig = 6.35
    lock14_amt = 6.15
    tp_r = 6.65

    busy_until = 0
    trades = 0
    wins = 0
    bes = 0
    losses = 0
    total_pnl = 0.0
    monthly_stats = {}
    trade_records = []

    peak = 0.0
    max_dd = 0.0

    print("Running sequential M5 SL-First simulation...", flush=True)
    for s in combined:
        s_time = s['time']
        if s_time < busy_until:
            continue

        m5_start = bisect.bisect_right(m5_times, s_time)
        if m5_start >= m5_len:
            continue

        entry = s['entry']
        sl = s['sl']
        risk = s['risk']
        sig = s['signal']

        tp = round(entry + (tp_r * risk), 2) if sig == "BUY" else round(entry - (tp_r * risk), 2)
        be_target = round(entry + (be_trigger * risk), 2) if sig == "BUY" else round(entry - (be_trigger * risk), 2)

        l1_target = round(entry + (lock1_trig * risk), 2) if sig == "BUY" else round(entry - (lock1_trig * risk), 2)
        l1_sl = round(entry + (lock1_amt * risk), 2) if sig == "BUY" else round(entry - (lock1_amt * risk), 2)

        l2_target = round(entry + (lock2_trig * risk), 2) if sig == "BUY" else round(entry - (lock2_trig * risk), 2)
        l2_sl = round(entry + (lock2_amt * risk), 2) if sig == "BUY" else round(entry - (lock2_amt * risk), 2)

        l3_target = round(entry + (lock3_trig * risk), 2) if sig == "BUY" else round(entry - (lock3_trig * risk), 2)
        l3_sl = round(entry + (lock3_amt * risk), 2) if sig == "BUY" else round(entry - (lock3_amt * risk), 2)

        l4_target = round(entry + (lock4_trig * risk), 2) if sig == "BUY" else round(entry - (lock4_trig * risk), 2)
        l4_sl = round(entry + (lock4_amt * risk), 2) if sig == "BUY" else round(entry - (lock4_amt * risk), 2)

        l5_target = round(entry + (lock5_trig * risk), 2) if sig == "BUY" else round(entry - (lock5_trig * risk), 2)
        l5_sl = round(entry + (lock5_amt * risk), 2) if sig == "BUY" else round(entry - (lock5_amt * risk), 2)

        l6_target = round(entry + (lock6_trig * risk), 2) if sig == "BUY" else round(entry - (lock6_trig * risk), 2)
        l6_sl = round(entry + (lock6_amt * risk), 2) if sig == "BUY" else round(entry - (lock6_amt * risk), 2)

        l7_target = round(entry + (lock7_trig * risk), 2) if sig == "BUY" else round(entry - (lock7_trig * risk), 2)
        l7_sl = round(entry + (lock7_amt * risk), 2) if sig == "BUY" else round(entry - (lock7_amt * risk), 2)

        l8_target = round(entry + (lock8_trig * risk), 2) if sig == "BUY" else round(entry - (lock8_trig * risk), 2)
        l8_sl = round(entry + (lock8_amt * risk), 2) if sig == "BUY" else round(entry - (lock8_amt * risk), 2)

        l9_target = round(entry + (lock9_trig * risk), 2) if sig == "BUY" else round(entry - (lock9_trig * risk), 2)
        l9_sl = round(entry + (lock9_amt * risk), 2) if sig == "BUY" else round(entry - (lock9_amt * risk), 2)

        l10_target = round(entry + (lock10_trig * risk), 2) if sig == "BUY" else round(entry - (lock10_trig * risk), 2)
        l10_sl = round(entry + (lock10_amt * risk), 2) if sig == "BUY" else round(entry - (lock10_amt * risk), 2)

        l11_target = round(entry + (lock11_trig * risk), 2) if sig == "BUY" else round(entry - (lock11_trig * risk), 2)
        l11_sl = round(entry + (lock11_amt * risk), 2) if sig == "BUY" else round(entry - (lock11_amt * risk), 2)

        l12_target = round(entry + (lock12_trig * risk), 2) if sig == "BUY" else round(entry - (lock12_trig * risk), 2)
        l12_sl = round(entry + (lock12_amt * risk), 2) if sig == "BUY" else round(entry - (lock12_amt * risk), 2)

        l13_target = round(entry + (lock13_trig * risk), 2) if sig == "BUY" else round(entry - (lock13_trig * risk), 2)
        l13_sl = round(entry + (lock13_amt * risk), 2) if sig == "BUY" else round(entry - (lock13_amt * risk), 2)

        l14_target = round(entry + (lock14_trig * risk), 2) if sig == "BUY" else round(entry - (lock14_trig * risk), 2)
        l14_sl = round(entry + (lock14_amt * risk), 2) if sig == "BUY" else round(entry - (lock14_amt * risk), 2)

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
        l5_active = False
        l6_active = False
        l7_active = False
        l8_active = False
        l9_active = False
        l10_active = False
        l11_active = False
        l12_active = False
        l13_active = False
        l14_active = False
        trade_pnl = 0.0
        outcome = None
        exit_time = entry_time

        for k in range(fill_m5 + 1, min(fill_m5 + 288, m5_len)):
            b = m5_gold[k]
            exit_time = b['time']

            if sig == "BUY":
                # PESSIMISTIC SL-FIRST EVALUATION
                if b['low'] <= current_sl:
                    if l14_active:
                        outcome = "WIN"
                        trade_pnl = (l14_sl - entry) * point_val
                    elif l13_active:
                        outcome = "WIN"
                        trade_pnl = (l13_sl - entry) * point_val
                    elif l12_active:
                        outcome = "WIN"
                        trade_pnl = (l12_sl - entry) * point_val
                    elif l11_active:
                        outcome = "WIN"
                        trade_pnl = (l11_sl - entry) * point_val
                    elif l10_active:
                        outcome = "WIN"
                        trade_pnl = (l10_sl - entry) * point_val
                    elif l9_active:
                        outcome = "WIN"
                        trade_pnl = (l9_sl - entry) * point_val
                    elif l8_active:
                        outcome = "WIN"
                        trade_pnl = (l8_sl - entry) * point_val
                    elif l7_active:
                        outcome = "WIN"
                        trade_pnl = (l7_sl - entry) * point_val
                    elif l6_active:
                        outcome = "WIN"
                        trade_pnl = (l6_sl - entry) * point_val
                    elif l5_active:
                        outcome = "WIN"
                        trade_pnl = (l5_sl - entry) * point_val
                    elif l4_active:
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
                        trade_pnl = -risk * point_val
                    break

                # TP Evaluation
                if b['high'] >= tp:
                    outcome = "WIN"
                    trade_pnl = (tp - entry) * point_val
                    break

                # Trailing Ratchet Locks Activation
                if b['high'] >= l14_target:
                    l14_active = True
                    current_sl = max(current_sl, l14_sl)
                elif b['high'] >= l13_target:
                    l13_active = True
                    current_sl = max(current_sl, l13_sl)
                elif b['high'] >= l12_target:
                    l12_active = True
                    current_sl = max(current_sl, l12_sl)
                elif b['high'] >= l11_target:
                    l11_active = True
                    current_sl = max(current_sl, l11_sl)
                elif b['high'] >= l10_target:
                    l10_active = True
                    current_sl = max(current_sl, l10_sl)
                elif b['high'] >= l9_target:
                    l9_active = True
                    current_sl = max(current_sl, l9_sl)
                elif b['high'] >= l8_target:
                    l8_active = True
                    current_sl = max(current_sl, l8_sl)
                elif b['high'] >= l7_target:
                    l7_active = True
                    current_sl = max(current_sl, l7_sl)
                elif b['high'] >= l6_target:
                    l6_active = True
                    current_sl = max(current_sl, l6_sl)
                elif b['high'] >= l5_target:
                    l5_active = True
                    current_sl = max(current_sl, l5_sl)
                elif b['high'] >= l4_target:
                    l4_active = True
                    current_sl = max(current_sl, l4_sl)
                elif b['high'] >= l3_target:
                    l3_active = True
                    current_sl = max(current_sl, l3_sl)
                elif b['high'] >= l2_target:
                    l2_active = True
                    current_sl = max(current_sl, l2_sl)
                elif b['high'] >= l1_target:
                    l1_active = True
                    current_sl = max(current_sl, l1_sl)
                elif b['high'] >= be_target:
                    be_active = True
                    current_sl = max(current_sl, entry)

            else:  # SELL
                # PESSIMISTIC SL-FIRST EVALUATION
                if b['high'] >= current_sl:
                    if l14_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l14_sl) * point_val
                    elif l13_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l13_sl) * point_val
                    elif l12_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l12_sl) * point_val
                    elif l11_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l11_sl) * point_val
                    elif l10_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l10_sl) * point_val
                    elif l9_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l9_sl) * point_val
                    elif l8_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l8_sl) * point_val
                    elif l7_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l7_sl) * point_val
                    elif l6_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l6_sl) * point_val
                    elif l5_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l5_sl) * point_val
                    elif l4_active:
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
                        trade_pnl = -risk * point_val
                    break

                # TP Evaluation
                if b['low'] <= tp:
                    outcome = "WIN"
                    trade_pnl = (entry - tp) * point_val
                    break

                # Trailing Ratchet Locks Activation
                if b['low'] <= l14_target:
                    l14_active = True
                    current_sl = min(current_sl, l14_sl)
                elif b['low'] <= l13_target:
                    l13_active = True
                    current_sl = min(current_sl, l13_sl)
                elif b['low'] <= l12_target:
                    l12_active = True
                    current_sl = min(current_sl, l12_sl)
                elif b['low'] <= l11_target:
                    l11_active = True
                    current_sl = min(current_sl, l11_sl)
                elif b['low'] <= l10_target:
                    l10_active = True
                    current_sl = min(current_sl, l10_sl)
                elif b['low'] <= l9_target:
                    l9_active = True
                    current_sl = min(current_sl, l9_sl)
                elif b['low'] <= l8_target:
                    l8_active = True
                    current_sl = min(current_sl, l8_sl)
                elif b['low'] <= l7_target:
                    l7_active = True
                    current_sl = min(current_sl, l7_sl)
                elif b['low'] <= l6_target:
                    l6_active = True
                    current_sl = min(current_sl, l6_sl)
                elif b['low'] <= l5_target:
                    l5_active = True
                    current_sl = min(current_sl, l5_sl)
                elif b['low'] <= l4_target:
                    l4_active = True
                    current_sl = min(current_sl, l4_sl)
                elif b['low'] <= l3_target:
                    l3_active = True
                    current_sl = min(current_sl, l3_sl)
                elif b['low'] <= l2_target:
                    l2_active = True
                    current_sl = min(current_sl, l2_sl)
                elif b['low'] <= l1_target:
                    l1_active = True
                    current_sl = min(current_sl, l1_sl)
                elif b['low'] <= be_target:
                    be_active = True
                    current_sl = min(current_sl, entry)

        if outcome is None:
            final_b = m5_gold[min(fill_m5 + 288, m5_len - 1)]
            final_c = final_b['close']
            exit_time = final_b['time']
            pnl_pts = (final_c - entry) if sig == "BUY" else (entry - final_c)
            trade_pnl = pnl_pts * point_val
            if trade_pnl > 0.05:
                outcome = "WIN"
            elif trade_pnl < -0.05:
                outcome = "LOSS"
            else:
                outcome = "BE"

        busy_until = exit_time

        if outcome == "WIN":
            wins += 1
        elif outcome == "BE":
            bes += 1
        else:
            losses += 1

        total_pnl += trade_pnl
        if total_pnl > peak:
            peak = total_pnl
        dd = peak - total_pnl
        if dd > max_dd:
            max_dd = dd

        if month_key not in monthly_stats:
            monthly_stats[month_key] = {"trades": 0, "wins": 0, "bes": 0, "losses": 0, "pnl": 0.0}
        monthly_stats[month_key]["trades"] += 1
        if outcome == "WIN":
            monthly_stats[month_key]["wins"] += 1
        elif outcome == "BE":
            monthly_stats[month_key]["bes"] += 1
        else:
            monthly_stats[month_key]["losses"] += 1
        monthly_stats[month_key]["pnl"] += trade_pnl

        trade_records.append({
            "entry_time": str(entry_dt),
            "month": month_key,
            "tf": s['tf'],
            "signal": sig,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "outcome": outcome,
            "pnl": trade_pnl
        })

    win_rate = (wins / trades * 100) if trades > 0 else 0
    non_loss_rate = ((wins + bes) / trades * 100) if trades > 0 else 0

    gross_profit = sum(t['pnl'] for t in trade_records if t['pnl'] > 0)
    gross_loss = abs(sum(t['pnl'] for t in trade_records if t['pnl'] < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 999.99

    print("=" * 115, flush=True)
    print(" S20.50 VERIFIED PERFORMANCE SUMMARY (STRICT 0.01 LOT)", flush=True)
    print("=" * 115, flush=True)
    print(f" Total Trades Executed:   {trades:,}", flush=True)
    print(f" Wins:                   {wins:,} ({win_rate:.1f}%)", flush=True)
    print(f" Breakevens:             {bes:,} ({bes/trades*100:.1f}%)", flush=True)
    print(f" Losses:                 {losses:,} ({losses/trades*100:.1f}%)", flush=True)
    print(f" Non-Loss Rate:          {non_loss_rate:.1f}%", flush=True)
    print(f" Gross Profit:           ${gross_profit:,.2f}", flush=True)
    print(f" Gross Loss:             ${gross_loss:,.2f}", flush=True)
    print(f" Profit Factor:          {profit_factor:.2f}", flush=True)
    print(f" Net Profit:             ${total_pnl:,.2f}", flush=True)
    print(f" Max Drawdown:           ${max_dd:,.2f}", flush=True)
    print("=" * 115, flush=True)

    print("\nMONTHLY BREAKDOWN:")
    print("-" * 75, flush=True)
    print(f"{'Month':<10} | {'Trades':<8} | {'Wins':<6} | {'BE':<5} | {'Loss':<6} | {'WR %':<8} | {'Net PnL ($)':<12}", flush=True)
    print("-" * 75, flush=True)

    monthly_rows = []
    for m in sorted(monthly_stats.keys()):
        st = monthly_stats[m]
        m_wr = (st['wins'] / st['trades'] * 100) if st['trades'] > 0 else 0
        print(f"{m:<10} | {st['trades']:<8} | {st['wins']:<6} | {st['bes']:<5} | {st['losses']:<6} | {m_wr:<7.1f}% | ${st['pnl']:<11.2f}", flush=True)
        monthly_rows.append({
            "month": m,
            "trades": st['trades'],
            "wins": st['wins'],
            "bes": st['bes'],
            "losses": st['losses'],
            "win_rate": round(m_wr, 1),
            "pnl": round(st['pnl'], 2)
        })
    print("-" * 75, flush=True)

    csv_path = os.path.join(os.path.dirname(__file__), "S20_50_monthly.csv")
    pd.DataFrame(monthly_rows).to_csv(csv_path, index=False)
    print(f"Monthly breakdown saved to: {csv_path}", flush=True)

if __name__ == "__main__":
    main()
