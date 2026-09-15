# -*- coding: utf-8 -*-
"""backtest_s20_29_runner.py — 365-Day Quantum Fusion Backtest:
Designed to decisively beat S20.28 ($2,226) Net Profit!
Modes:
1. Mode 1: S20.28 Benchmark (TP1 1.8R, Lock +0.8R, TP2 4.0R)
2. Mode 2: Stepped Macro Runner (Lock +0.8R at 1.8R, Lock +1.8R at 2.8R, Target 5.5R)
3. Mode 3: Conviction-Weighted (A+ Grade gets 0.03 Lot, Standard gets 0.02 Lot)
4. Mode 4: Dual-Horizon Synergy (M15 + M30 Combined Feed with Intelligent Dedup)
"""

import argparse
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

import strategy20_29


def init_mt5():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()


def simulate_single_feed(rates, df, mode="mode_stepped_macro", base_lot=0.02, tf_name="M30"):
    contract_size = 100.0

    trades = 0
    full_wins = 0
    scalp_wins = 0
    full_losses = 0
    breakevens = 0
    pnl = 0.0
    max_pnl = 0.0
    max_dd = 0.0
    trade_records = []

    i = 45
    n = len(rates)

    while i < n - 5:
        res = strategy20_29.evaluate_s20_29_bar(df, i, tf=tf_name)
        if not res:
            i += 1
            continue

        sig = res["signal"]
        entry = res["entry"]
        sl = res["sl"]
        risk = res["risk"]
        is_a_plus = res.get("is_a_plus", False)

        # Conviction lot sizing
        if mode == "mode_conviction_weighted":
            total_lot = 0.03 if is_a_plus else base_lot
        else:
            total_lot = base_lot

        scalp_lot = total_lot * 0.5
        runner_lot = total_lot * 0.5
        val_scalp = contract_size * scalp_lot
        val_runner = contract_size * runner_lot

        tp1 = res["tp_scalp"]
        be_trig = entry + ((tp1 - entry) * res.get("be_ratio", 0.40)) if sig == "BUY" else entry - ((entry - tp1) * res.get("be_ratio", 0.40))

        # Runner Target configuration
        if mode == "mode_s28_bench":
            tp2 = entry + (4.0 * risk) if sig == "BUY" else entry - (4.0 * risk)
            step2_trig = None
        else:
            # Stepped Macro: Aim for 5.5R
            tp2 = entry + (5.5 * risk) if sig == "BUY" else entry - (5.5 * risk)
            step2_trig = entry + (2.8 * risk) if sig == "BUY" else entry - (2.8 * risk)

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

        tp1_hit = False
        step2_active = False
        be_active = False
        runner_sl = sl
        trade_pnl = 0.0
        bars_held = 0
        outcome = None

        for bar in active:
            bars_held += 1
            if sig == "BUY":
                # BE trigger
                if not be_active and bar['high'] >= be_trig:
                    be_active = True
                    runner_sl = entry

                # TP1 hit
                if not tp1_hit and bar['high'] >= tp1:
                    tp1_hit = True
                    be_active = True
                    runner_sl = entry + (0.80 * risk)  # Lock +0.8R
                    trade_pnl += abs(tp1 - entry) * val_scalp

                # Step 2 lock (+1.8R at 2.8R)
                if tp1_hit and step2_trig is not None and not step2_active and bar['high'] >= step2_trig:
                    step2_active = True
                    runner_sl = entry + (1.80 * risk)  # Lock +1.8R!

                # TP2 hit
                if tp1_hit and bar['high'] >= tp2:
                    trade_pnl += abs(tp2 - entry) * val_runner
                    outcome = "FULL_WIN"
                    break

                # SL hit
                if bar['low'] <= runner_sl:
                    if not tp1_hit:
                        if be_active:
                            outcome = "BE"
                        else:
                            outcome = "LOSS"
                            trade_pnl = -abs(entry - runner_sl) * (val_scalp + val_runner)
                    else:
                        outcome = "SCALP_WIN"
                        locked_pnl = (runner_sl - entry) * val_runner
                        trade_pnl += locked_pnl
                    break

            else:  # SELL
                if not be_active and bar['low'] <= be_trig:
                    be_active = True
                    runner_sl = entry

                if not tp1_hit and bar['low'] <= tp1:
                    tp1_hit = True
                    be_active = True
                    runner_sl = entry - (0.80 * risk)
                    trade_pnl += abs(entry - tp1) * val_scalp

                if tp1_hit and step2_trig is not None and not step2_active and bar['low'] <= step2_trig:
                    step2_active = True
                    runner_sl = entry - (1.80 * risk)

                if tp1_hit and bar['low'] <= tp2:
                    trade_pnl += abs(entry - tp2) * val_runner
                    outcome = "FULL_WIN"
                    break

                if bar['high'] >= runner_sl:
                    if not tp1_hit:
                        if be_active:
                            outcome = "BE"
                        else:
                            outcome = "LOSS"
                            trade_pnl = -abs(runner_sl - entry) * (val_scalp + val_runner)
                    else:
                        outcome = "SCALP_WIN"
                        locked_pnl = (entry - runner_sl) * val_runner
                        trade_pnl += locked_pnl
                    break

        if outcome == "FULL_WIN":
            full_wins += 1
        elif outcome == "SCALP_WIN":
            scalp_wins += 1
        elif outcome == "LOSS":
            full_losses += 1
        else:
            breakevens += 1

        pnl += trade_pnl
        if pnl > max_pnl:
            max_pnl = pnl
        dd = max_pnl - pnl
        if dd > max_dd:
            max_dd = dd

        trade_records.append({
            "time": str(entry_time),
            "timestamp": int(future[fill_idx]['time']),
            "month": month_key,
            "signal": sig,
            "is_a_plus": is_a_plus,
            "outcome": outcome,
            "pnl": trade_pnl,
            "bars_held": bars_held
        })

        i += (fill_idx + max(1, bars_held // 2))

    gross_win = sum(r['pnl'] for r in trade_records if r['pnl'] > 0)
    gross_loss = abs(sum(r['pnl'] for r in trade_records if r['pnl'] < 0))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (99.9 if gross_win > 0 else 0.0)

    if trade_records:
        t_df = pd.DataFrame(trade_records)
        m_grouped = t_df.groupby('month')['pnl'].sum()
        pos_months = (m_grouped > 0).sum()
        tot_months = len(m_grouped)
        m_pct = (pos_months / tot_months * 100.0) if tot_months > 0 else 0.0
    else:
        pos_months, tot_months, m_pct = 0, 0, 0.0

    effective_wr = ((full_wins + scalp_wins) / trades * 100.0) if trades > 0 else 0.0

    return {
        "mode": mode,
        "tf": tf_name,
        "trades": trades,
        "full_wins": full_wins,
        "scalp_wins": scalp_wins,
        "breakevens": breakevens,
        "full_losses": full_losses,
        "effective_wr": effective_wr,
        "net_pnl": pnl,
        "pf": pf,
        "max_dd": max_dd,
        "pos_months": pos_months,
        "tot_months": tot_months,
        "month_wr_pct": m_pct,
        "records": trade_records
    }


def simulate_dual_horizon(m15_rates, m15_df, m30_rates, m30_df, base_lot=0.02):
    """Combine M15 and M30 feeds with intelligent deduplication."""
    res_m15 = simulate_single_feed(m15_rates, m15_df, mode="mode_stepped_macro", base_lot=base_lot, tf_name="M15")
    res_m30 = simulate_single_feed(m30_rates, m30_df, mode="mode_stepped_macro", base_lot=base_lot, tf_name="M30")

    rec15 = res_m15["records"]
    rec30 = res_m30["records"]

    # Deduplicate: if an M30 trade starts within 1800s (30m) of an M15 trade, keep only M15
    combined = []
    m15_times = [r['timestamp'] for r in rec15]

    combined.extend(rec15)
    for r30 in rec30:
        ts = r30['timestamp']
        # Check if any m15 trade within 1800s
        clash = any(abs(ts - m_ts) <= 1800 for m_ts in m15_times)
        if not clash:
            combined.append(r30)

    # Sort combined by timestamp
    combined.sort(key=lambda x: x['timestamp'])

    # Recalculate metrics
    trades = len(combined)
    full_wins = sum(1 for r in combined if r['outcome'] == 'FULL_WIN')
    scalp_wins = sum(1 for r in combined if r['outcome'] == 'SCALP_WIN')
    breakevens = sum(1 for r in combined if r['outcome'] == 'BE')
    full_losses = sum(1 for r in combined if r['outcome'] == 'LOSS')

    pnl = 0.0
    max_pnl = 0.0
    max_dd = 0.0
    for r in combined:
        pnl += r['pnl']
        if pnl > max_pnl:
            max_pnl = pnl
        dd = max_pnl - pnl
        if dd > max_dd:
            max_dd = dd

    gross_win = sum(r['pnl'] for r in combined if r['pnl'] > 0)
    gross_loss = abs(sum(r['pnl'] for r in combined if r['pnl'] < 0))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (99.9 if gross_win > 0 else 0.0)

    t_df = pd.DataFrame(combined)
    m_grouped = t_df.groupby('month')['pnl'].sum()
    pos_months = (m_grouped > 0).sum()
    tot_months = len(m_grouped)
    m_pct = (pos_months / tot_months * 100.0) if tot_months > 0 else 0.0

    effective_wr = ((full_wins + scalp_wins) / trades * 100.0) if trades > 0 else 0.0

    return {
        "mode": "mode_dual_horizon",
        "tf": "M15+M30",
        "trades": trades,
        "full_wins": full_wins,
        "scalp_wins": scalp_wins,
        "breakevens": breakevens,
        "full_losses": full_losses,
        "effective_wr": effective_wr,
        "net_pnl": pnl,
        "pf": pf,
        "max_dd": max_dd,
        "pos_months": pos_months,
        "tot_months": tot_months,
        "month_wr_pct": m_pct,
        "records": combined
    }


def main():
    parser = argparse.ArgumentParser(description="Run S20.29 Quantum Fusion Backtest")
    parser.add_argument("--days", type=int, default=365, help="Backtest days")
    args = parser.parse_args()

    if not init_mt5():
        print("[ERROR] Failed to initialize MT5")
        return

    symbol_gold = "XAUUSD.iux"
    symbol_silver = "XAGUSD.iux"

    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=args.days)

    print(f"\n================================================================================")
    print(f" S20.29 APEX QUANTUM FUSION — ULTIMATE PROFIT EXPANSION (365 DAYS)")
    print(f" Target: Beat S20.28 ($2,126 - $2,226) Net Profit with Low Drawdown")
    print(f"================================================================================")

    m30_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M30, start_dt, now)
    m30_silver = mt5.copy_rates_range(symbol_silver, mt5.TIMEFRAME_M30, start_dt, now)

    m15_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M15, start_dt, now)
    m15_silver = mt5.copy_rates_range(symbol_silver, mt5.TIMEFRAME_M15, start_dt, now)

    mt5.shutdown()

    if m30_gold is None or len(m30_gold) == 0:
        print("[ERROR] Failed to load Gold data")
        return

    print(f"Loaded: M30 Gold {len(m30_gold)} | M15 Gold {len(m15_gold)}")
    print("Computing indicators...")

    m30_df = strategy20_29.compute_indicators_df(m30_gold, m30_silver)
    m15_df = strategy20_29.compute_indicators_df(m15_gold, m15_silver)

    results = []

    # 1. M30 Stepped Macro Runner
    res_m30_stepped = simulate_single_feed(m30_gold, m30_df, mode="mode_stepped_macro", tf_name="M30")
    results.append(res_m30_stepped)

    # 2. M15 Stepped Macro Runner
    res_m15_stepped = simulate_single_feed(m15_gold, m15_df, mode="mode_stepped_macro", tf_name="M15")
    results.append(res_m15_stepped)

    # 3. M30 Conviction Weighted
    res_m30_conv = simulate_single_feed(m30_gold, m30_df, mode="mode_conviction_weighted", tf_name="M30")
    results.append(res_m30_conv)

    # 4. M15 Conviction Weighted
    res_m15_conv = simulate_single_feed(m15_gold, m15_df, mode="mode_conviction_weighted", tf_name="M15")
    results.append(res_m15_conv)

    # 5. Dual Horizon Synergy (M15 + M30 Combined)
    res_dual = simulate_dual_horizon(m15_gold, m15_df, m30_gold, m30_df)
    results.append(res_dual)

    for r in results:
        print(f"\n>>> [{r['tf']}] Mode: {r['mode']}")
        print(f"    Trades: {r['trades']} | Win Rate: {r['effective_wr']:.1f}%")
        print(f"    Full Wins: {r['full_wins']} | Scalp Wins: {r['scalp_wins']} | BEs: {r['breakevens']} | Full Losses: {r['full_losses']}")
        print(f"    Net Profit: ${r['net_pnl']:.2f} | PF: {r['pf']:.2f} | MaxDD: ${r['max_dd']:.2f}")
        print(f"    Profitable Months: {r['pos_months']}/{r['tot_months']} ({r['month_wr_pct']:.1f}%)")

    summary_df = pd.DataFrame([
        {
            "Mode": r["mode"],
            "TF": r["tf"],
            "Trades": r["trades"],
            "WinRate%": round(r["effective_wr"], 1),
            "FullWins": r["full_wins"],
            "ScalpWins": r["scalp_wins"],
            "BEs": r["breakevens"],
            "Losses": r["full_losses"],
            "NetPnL($)": round(r["net_pnl"], 2),
            "PF": round(r["pf"], 2),
            "MaxDD($)": round(r["max_dd"], 2),
            "WinMonths": f"{r['pos_months']}/{r['tot_months']}"
        }
        for r in results
    ])

    out_csv = os.path.join(current_dir, "S20_29_matrix_comparison.csv")
    summary_df.to_csv(out_csv, index=False)
    print(f"\nSaved comparison to: {out_csv}")
    print(f"\nSummary Matrix Table:\n{summary_df.to_string(index=False)}")


if __name__ == "__main__":
    main()
