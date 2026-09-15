# -*- coding: utf-8 -*-
"""backtest_s20_28_runner.py — 365-Day Backtest for S20.28 Hyper-Confluence:
Explores 4 Advanced Runner Trailing & Scale-Out Engines to beat S20.26 Net Profit!
1. Mode 1: Benchmark Static BE (S20.26 baseline)
2. Mode 2: Profit-Lock Step (+0.8R locked at TP1, TP2 4.0R)
3. Mode 3: Dynamic 3-Bar Swing Trail (Locks +0.6R at TP1, trails swing H/L)
4. Mode 4: Tri-Tier Scaling (TP1 1.5R 40% / TP2 3.0R 30% / TP3 6.0R 30%)
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

import strategy20_28


def init_mt5():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()


def simulate_s20_28(gold_rates, df, mode="mode_dynamic_swing_trail", total_lot=0.02, tf_name="M30"):
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
    n = len(gold_rates)

    while i < n - 5:
        res = strategy20_28.evaluate_s20_28_bar(df, i, tf=tf_name)
        if not res:
            i += 1
            continue

        sig = res["signal"]
        entry = res["entry"]
        sl = res["sl"]
        risk = res["risk"]
        atr = res["atr"]
        tp1 = res["tp_scalp"]
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

        trade_pnl = 0.0
        outcome = None
        bars_held = 0

        # ---------------------------------------------------------------------
        # EXECUTION BY TRAILING MODE
        # ---------------------------------------------------------------------
        if mode == "mode_static_be":
            # S20.26 Baseline
            scalp_lot = total_lot * 0.5
            runner_lot = total_lot * 0.5
            val_scalp = contract_size * scalp_lot
            val_runner = contract_size * runner_lot

            tp2 = res["tp_runner"]
            tp1_hit = False
            be_active = False
            runner_sl = sl

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
                        trade_pnl += abs(tp1 - entry) * val_scalp
                    if tp1_hit and bar['high'] >= tp2:
                        trade_pnl += abs(tp2 - entry) * val_runner
                        outcome = "FULL_WIN"
                        break
                    if bar['low'] <= runner_sl:
                        if not tp1_hit:
                            if be_active:
                                outcome = "BE"
                            else:
                                outcome = "LOSS"
                                trade_pnl = -abs(entry - runner_sl) * (val_scalp + val_runner)
                        else:
                            outcome = "SCALP_WIN"
                            trade_pnl += 0.30 * val_runner
                        break

                else:  # SELL
                    if not be_active and bar['low'] <= be_trig:
                        be_active = True
                        runner_sl = entry
                    if not tp1_hit and bar['low'] <= tp1:
                        tp1_hit = True
                        be_active = True
                        runner_sl = entry - 0.30
                        trade_pnl += abs(entry - tp1) * val_scalp
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
                            trade_pnl += 0.30 * val_runner
                        break

        elif mode == "mode_profit_lock":
            # Lock +0.8R at TP1, aim for 4.0R
            scalp_lot = total_lot * 0.5
            runner_lot = total_lot * 0.5
            val_scalp = contract_size * scalp_lot
            val_runner = contract_size * runner_lot

            tp2 = entry + (4.0 * risk) if sig == "BUY" else entry - (4.0 * risk)
            tp1_hit = False
            be_active = False
            runner_sl = sl

            for bar in active:
                bars_held += 1
                if sig == "BUY":
                    if not be_active and bar['high'] >= be_trig:
                        be_active = True
                        runner_sl = entry
                    if not tp1_hit and bar['high'] >= tp1:
                        tp1_hit = True
                        be_active = True
                        runner_sl = entry + (0.80 * risk)  # Lock 0.8R
                        trade_pnl += abs(tp1 - entry) * val_scalp
                    if tp1_hit and bar['high'] >= tp2:
                        trade_pnl += abs(tp2 - entry) * val_runner
                        outcome = "FULL_WIN"
                        break
                    if bar['low'] <= runner_sl:
                        if not tp1_hit:
                            if be_active:
                                outcome = "BE"
                            else:
                                outcome = "LOSS"
                                trade_pnl = -abs(entry - runner_sl) * (val_scalp + val_runner)
                        else:
                            outcome = "SCALP_WIN"
                            trade_pnl += (0.80 * risk) * val_runner
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
                            trade_pnl += (0.80 * risk) * val_runner
                        break

        elif mode == "mode_dynamic_swing_trail":
            # Dynamic Trailing behind 3-bar swing after TP1
            scalp_lot = total_lot * 0.5
            runner_lot = total_lot * 0.5
            val_scalp = contract_size * scalp_lot
            val_runner = contract_size * runner_lot

            tp2 = entry + (5.0 * risk) if sig == "BUY" else entry - (5.0 * risk)
            tp1_hit = False
            be_active = False
            runner_sl = sl
            recent_lows = []
            recent_highs = []

            for bar in active:
                bars_held += 1
                recent_lows.append(bar['low'])
                recent_highs.append(bar['high'])

                if sig == "BUY":
                    if not be_active and bar['high'] >= be_trig:
                        be_active = True
                        runner_sl = entry
                    if not tp1_hit and bar['high'] >= tp1:
                        tp1_hit = True
                        be_active = True
                        runner_sl = entry + (0.50 * risk)
                        trade_pnl += abs(tp1 - entry) * val_scalp

                    # Dynamic trailing
                    if tp1_hit and len(recent_lows) >= 3:
                        trail_candidate = min(recent_lows[-3:]) - 0.20
                        if trail_candidate > runner_sl:
                            runner_sl = trail_candidate

                    if tp1_hit and bar['high'] >= tp2:
                        trade_pnl += abs(tp2 - entry) * val_runner
                        outcome = "FULL_WIN"
                        break
                    if bar['low'] <= runner_sl:
                        if not tp1_hit:
                            if be_active:
                                outcome = "BE"
                            else:
                                outcome = "LOSS"
                                trade_pnl = -abs(entry - runner_sl) * (val_scalp + val_runner)
                        else:
                            outcome = "SCALP_WIN"
                            trade_pnl += (runner_sl - entry) * val_runner
                        break

                else:  # SELL
                    if not be_active and bar['low'] <= be_trig:
                        be_active = True
                        runner_sl = entry
                    if not tp1_hit and bar['low'] <= tp1:
                        tp1_hit = True
                        be_active = True
                        runner_sl = entry - (0.50 * risk)
                        trade_pnl += abs(entry - tp1) * val_scalp

                    if tp1_hit and len(recent_highs) >= 3:
                        trail_candidate = max(recent_highs[-3:]) + 0.20
                        if trail_candidate < runner_sl:
                            runner_sl = trail_candidate

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
                            trade_pnl += (entry - runner_sl) * val_runner
                        break

        elif mode == "mode_tri_tier":
            # Tri-tier scale out: 40% at 1.5R, 30% at 3.0R, 30% at 5.5R
            lot1 = total_lot * 0.40
            lot2 = total_lot * 0.30
            lot3 = total_lot * 0.30
            val1 = contract_size * lot1
            val2 = contract_size * lot2
            val3 = contract_size * lot3

            t_target1 = entry + (1.5 * risk) if sig == "BUY" else entry - (1.5 * risk)
            t_target2 = entry + (3.0 * risk) if sig == "BUY" else entry - (3.0 * risk)
            t_target3 = entry + (5.5 * risk) if sig == "BUY" else entry - (5.5 * risk)

            t1_done = False
            t2_done = False
            t3_done = False
            be_active = False
            pos_sl = sl

            for bar in active:
                bars_held += 1
                if sig == "BUY":
                    if not be_active and bar['high'] >= be_trig:
                        be_active = True
                        pos_sl = entry

                    if not t1_done and bar['high'] >= t_target1:
                        t1_done = True
                        be_active = True
                        pos_sl = entry + 0.30
                        trade_pnl += (t_target1 - entry) * val1

                    if t1_done and not t2_done and bar['high'] >= t_target2:
                        t2_done = True
                        pos_sl = entry + (1.2 * risk)  # Lock 1.2R for tier 3
                        trade_pnl += (t_target2 - entry) * val2

                    if t2_done and not t3_done and bar['high'] >= t_target3:
                        t3_done = True
                        trade_pnl += (t_target3 - entry) * val3
                        outcome = "FULL_WIN"
                        break

                    if bar['low'] <= pos_sl:
                        rem_val = (0.0 if t1_done else val1) + (0.0 if t2_done else val2) + (0.0 if t3_done else val3)
                        if not t1_done:
                            if be_active:
                                outcome = "BE"
                            else:
                                outcome = "LOSS"
                                trade_pnl = -abs(entry - pos_sl) * rem_val
                        else:
                            outcome = "SCALP_WIN"
                            trade_pnl += (pos_sl - entry) * rem_val
                        break

                else:  # SELL
                    if not be_active and bar['low'] <= be_trig:
                        be_active = True
                        pos_sl = entry

                    if not t1_done and bar['low'] <= t_target1:
                        t1_done = True
                        be_active = True
                        pos_sl = entry - 0.30
                        trade_pnl += (entry - t_target1) * val1

                    if t1_done and not t2_done and bar['low'] <= t_target2:
                        t2_done = True
                        pos_sl = entry - (1.2 * risk)
                        trade_pnl += (entry - t_target2) * val2

                    if t2_done and not t3_done and bar['low'] <= t_target3:
                        t3_done = True
                        trade_pnl += (entry - t_target3) * val3
                        outcome = "FULL_WIN"
                        break

                    if bar['high'] >= pos_sl:
                        rem_val = (0.0 if t1_done else val1) + (0.0 if t2_done else val2) + (0.0 if t3_done else val3)
                        if not t1_done:
                            if be_active:
                                outcome = "BE"
                            else:
                                outcome = "LOSS"
                                trade_pnl = -abs(pos_sl - entry) * rem_val
                        else:
                            outcome = "SCALP_WIN"
                            trade_pnl += (entry - pos_sl) * rem_val
                        break

        # Record outcome
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
    parser = argparse.ArgumentParser(description="Run S20.28 Runner Exploration")
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
    print(f" S20.28 HYPER-CONFLUENCE — RUNNER UNLOCK MATRIX (365 DAYS)")
    print(f" Symbol Gold: {symbol_gold} | Silver: {symbol_silver} | TF: {args.tf} | Days: {args.days}")
    print(f"================================================================================")

    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=args.days)

    gold_rates = mt5.copy_rates_range(symbol_gold, mt5_tf, start_dt, now)
    silver_rates = mt5.copy_rates_range(symbol_silver, mt5_tf, start_dt, now)

    mt5.shutdown()

    if gold_rates is None or len(gold_rates) == 0:
        print("[ERROR] Could not fetch Gold rates")
        return
    if silver_rates is None or len(silver_rates) == 0:
        silver_rates = None

    print(f"Loaded Gold bars: {len(gold_rates)} | Silver: {len(silver_rates) if silver_rates is not None else 0}")
    print("Computing indicators...")
    df = strategy20_28.compute_indicators_df(gold_rates, silver_rates)

    modes = [
        ("mode_static_be", "Mode 1: S20.26 Benchmark (Static BE +0.30)"),
        ("mode_profit_lock", "Mode 2: Profit-Lock Step (+0.8R Locked at TP1)"),
        ("mode_dynamic_swing_trail", "Mode 3: Dynamic 3-Bar Swing Trail"),
        ("mode_tri_tier", "Mode 4: Tri-Tier Scale-Out (1.5R / 3.0R / 5.5R)")
    ]

    results = []
    print(f"\n{'-'*80}")
    print(f" RUNNING MATRIX COMPARISON ACROSS {args.days} DAYS...")
    print(f"{'-'*80}")

    for m_key, m_desc in modes:
        res = simulate_s20_28(gold_rates, df, mode=m_key, total_lot=0.02, tf_name=args.tf)
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

    out_csv = os.path.join(current_dir, "S20_28_matrix_comparison.csv")
    summary_df.to_csv(out_csv, index=False)
    print(f"\nSaved comparison to: {out_csv}")
    print(f"\nSummary Matrix Table:\n{summary_df.to_string(index=False)}")


if __name__ == "__main__":
    main()
