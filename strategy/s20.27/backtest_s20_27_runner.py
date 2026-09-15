# -*- coding: utf-8 -*-
"""backtest_s20_27_runner.py — 365-Day Backtest & Matrix Analysis for S20.27 Omni-Nexus:
Evaluates whether adding:
1. ICT Fair Value Gap (FVG) Displacement Retest
2. Multi-Timeframe H1 Trend Guard
3. Dynamic Regime Runner (4.5R+)
strictly enhances the performance over S20.26!
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

import strategy20_27


def init_mt5():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()


def simulate_s20_27(gold_rates, df, mode="nexus_ultimate", total_lot=0.02, tf_name="M30"):
    contract_size = 100.0
    scalp_lot = total_lot / 2.0
    runner_lot = total_lot / 2.0
    point_val_scalp = contract_size * scalp_lot
    point_val_runner = contract_size * runner_lot

    trades = 0
    full_wins = 0      # Both TP1 & TP2 hit
    scalp_wins = 0     # TP1 hit, Runner BE
    full_losses = 0    # Stopped out before TP1
    breakevens = 0     # Stopped out at BE before TP1
    pnl = 0.0
    max_pnl = 0.0
    max_dd = 0.0
    trade_records = []

    i = 45
    n = len(gold_rates)

    while i < n - 5:
        res = strategy20_27.evaluate_s20_27_bar(df, i, tf=tf_name, mode=mode)
        if not res:
            i += 1
            continue

        sig = res["signal"]
        entry = res["entry"]
        sl = res["sl"]
        tp1 = res["tp_scalp"]
        tp2 = res["tp_runner"]
        be_trig = entry + ((tp1 - entry) * res.get("be_ratio", 0.40)) if sig == "BUY" else entry - ((entry - tp1) * res.get("be_ratio", 0.40))

        future = gold_rates[i + 1:]
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
        tp2_hit = False
        be_active = False
        runner_sl = sl
        trade_pnl = 0.0
        bars_held = 0
        outcome = None

        for bar in active:
            bars_held += 1
            if sig == "BUY":
                if not be_active and bar['high'] >= be_trig:
                    be_active = True
                    runner_sl = entry

                if not tp1_hit and bar['high'] >= tp1:
                    tp1_hit = True
                    be_active = True
                    runner_sl = entry + 0.30
                    trade_pnl += abs(tp1 - entry) * point_val_scalp

                if tp1_hit and not tp2_hit and bar['high'] >= tp2:
                    tp2_hit = True
                    trade_pnl += abs(tp2 - entry) * point_val_runner
                    outcome = "FULL_WIN"
                    break

                if bar['low'] <= runner_sl:
                    if not tp1_hit:
                        if be_active:
                            outcome = "BE"
                            trade_pnl = 0.0
                        else:
                            outcome = "LOSS"
                            trade_pnl = -abs(entry - runner_sl) * (point_val_scalp + point_val_runner)
                    else:
                        outcome = "SCALP_WIN"
                        trade_pnl += 0.30 * point_val_runner
                    break

            elif sig == "SELL":
                if not be_active and bar['low'] <= be_trig:
                    be_active = True
                    runner_sl = entry

                if not tp1_hit and bar['low'] <= tp1:
                    tp1_hit = True
                    be_active = True
                    runner_sl = entry - 0.30
                    trade_pnl += abs(entry - tp1) * point_val_scalp

                if tp1_hit and not tp2_hit and bar['low'] <= tp2:
                    tp2_hit = True
                    trade_pnl += abs(entry - tp2) * point_val_runner
                    outcome = "FULL_WIN"
                    break

                if bar['high'] >= runner_sl:
                    if not tp1_hit:
                        if be_active:
                            outcome = "BE"
                            trade_pnl = 0.0
                        else:
                            outcome = "LOSS"
                            trade_pnl = -abs(runner_sl - entry) * (point_val_scalp + point_val_runner)
                    else:
                        outcome = "SCALP_WIN"
                        trade_pnl += 0.30 * point_val_runner
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
            "month": month_key,
            "signal": sig,
            "reason": res["reason"],
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


def main():
    parser = argparse.ArgumentParser(description="Run S20.27 Omni-Nexus Backtest")
    parser.add_argument("--days", type=int, default=365, help="Backtest days")
    parser.add_argument("--tf", type=str, default="M30", help="Timeframe (M15 or M30)")
    args = parser.parse_args()

    if not init_mt5():
        print("[ERROR] Failed to initialize MT5")
        return

    symbol_gold = "XAUUSD.iux"
    symbol_silver = "XAGUSD.iux"
    tf_map = {
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1
    }
    mt5_tf = tf_map.get(args.tf, mt5.TIMEFRAME_M30)

    print(f"\n================================================================================")
    print(f" S20.27 OMNI-INSTITUTIONAL NEXUS — 365-DAY FUSION ANALYSIS")
    print(f" Symbol Gold: {symbol_gold} | Silver: {symbol_silver} | TF: {args.tf} | Days: {args.days}")
    print(f"================================================================================")

    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=args.days)

    gold_rates = mt5.copy_rates_range(symbol_gold, mt5_tf, start_dt, now)
    silver_rates = mt5.copy_rates_range(symbol_silver, mt5_tf, start_dt, now)
    h1_rates = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H1, start_dt, now)

    mt5.shutdown()

    if gold_rates is None or len(gold_rates) == 0:
        print("[ERROR] Could not fetch Gold rates")
        return
    if silver_rates is None or len(silver_rates) == 0:
        print("[WARNING] Could not fetch Silver rates, running single-asset")
        silver_rates = None

    print(f"Loaded Gold bars: {len(gold_rates)} | Silver: {len(silver_rates) if silver_rates is not None else 0} | H1: {len(h1_rates) if h1_rates is not None else 0}")
    print("Computing indicators & multi-timeframe fractal alignments...")
    df = strategy20_27.compute_indicators_df(gold_rates, silver_rates, h1_rates)

    modes = [
        ("benchmark_s26", "Mode 1: S20.26 Benchmark (Quad Apex)"),
        ("nexus_fvg", "Mode 2: Nexus + FVG Displacement Retest"),
        ("nexus_htf", "Mode 3: Nexus + H1 Trend Guard"),
        ("nexus_ultimate", "Mode 4: Omni-Nexus Ultimate (Complete Fusion)")
    ]

    results = []
    print(f"\n{'-'*80}")
    print(f" RUNNING MATRIX COMPARISON ACROSS {args.days} DAYS...")
    print(f"{'-'*80}")

    for m_key, m_desc in modes:
        res = simulate_s20_27(gold_rates, df, mode=m_key, total_lot=0.02, tf_name=args.tf)
        results.append(res)
        print(f"\n>>> {m_desc}")
        print(f"    Trades: {res['trades']} | Win Rate: {res['effective_wr']:.1f}%")
        print(f"    Full Wins: {res['full_wins']} | Scalp Wins: {res['scalp_wins']} | BEs: {res['breakevens']} | Full Losses: {res['full_losses']}")
        print(f"    Net Profit: ${res['net_pnl']:.2f} | PF: {res['pf']:.2f} | MaxDD: ${res['max_dd']:.2f}")
        print(f"    Profitable Months: {res['pos_months']}/{res['tot_months']} ({res['month_wr_pct']:.1f}%)")

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

    out_csv = os.path.join(current_dir, "S20_27_matrix_comparison.csv")
    summary_df.to_csv(out_csv, index=False)
    print(f"\nSaved comparison to: {out_csv}")
    print(f"\nSummary Matrix Table:\n{summary_df.to_string(index=False)}")


if __name__ == "__main__":
    main()
