# -*- coding: utf-8 -*-
"""backtest_s20_30_runner.py — 365-Day Synergy Comparison (Strict Lot 0.01):
Answers:
"Strategy ไหนใช้ร่วมกันแล้ว work ไม่ใช่ว่าทำงานแยกกันนะ หมายถึงทำงานร่วมกันแล้วแม่นขึ้น"
Under strict constraint: Single 0.01 Lot position (no partial lot splits).

Compares 5 Multi-Strategy Synergy Combinations on the exact same market bars:
1. Combo A: Pure Liquidity Sweep + Volume Climax (Baseline)
2. Combo B: Liquidity Sweep + Intermarket SMT Divergence (Gold vs Silver)
3. Combo C: Liquidity Sweep + Session Anchored VWAP (Statistical Extremes)
4. Combo D: Liquidity Sweep + RSI(14) Divergence (Momentum Exhaustion)
5. Combo E: Grand Confluence Matrix (Sweep + SMT + VWAP + RSI + Volume)
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

import strategy20_30


def init_mt5():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()


def simulate_synergy_combo(rates, df, combo_name="combo_grand_synergy", tf_name="M30"):
    """Simulate single position at strictly 0.01 lot."""
    lot = 0.01
    contract_size = 100.0
    point_val = contract_size * lot  # 1.0 USD per $1.00 move

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
        res = strategy20_30.evaluate_s20_30_bar(df, i, combo=combo_name)
        if not res:
            i += 1
            continue

        sig = res["signal"]
        entry = res["entry"]
        sl = res["sl"]
        risk = res["risk"]

        # Targets for single 0.01 lot position
        tp1 = entry + (1.8 * risk) if sig == "BUY" else entry - (1.8 * risk)
        tp2 = entry + (4.0 * risk) if sig == "BUY" else entry - (4.0 * risk)
        be_trig = entry + ((tp1 - entry) * res.get("be_ratio", 0.40)) if sig == "BUY" else entry - ((entry - tp1) * res.get("be_ratio", 0.40))

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

        be_active = False
        profit_lock_active = False
        current_sl = sl
        trade_pnl = 0.0
        bars_held = 0
        outcome = None

        for bar in active:
            bars_held += 1
            if sig == "BUY":
                # BE Trigger (at 40% towards TP1)
                if not be_active and bar['high'] >= be_trig:
                    be_active = True
                    current_sl = entry

                # Profit-Lock Step (at TP1 1.8R, lock +0.8R)
                if not profit_lock_active and bar['high'] >= tp1:
                    profit_lock_active = True
                    current_sl = entry + (0.80 * risk)

                # Full TP2 hit (4.0R)
                if bar['high'] >= tp2:
                    trade_pnl = abs(tp2 - entry) * point_val
                    outcome = "FULL_WIN"
                    break

                # SL hit
                if bar['low'] <= current_sl:
                    if profit_lock_active:
                        outcome = "PROFIT_LOCK_WIN"
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

                if not profit_lock_active and bar['low'] <= tp1:
                    profit_lock_active = True
                    current_sl = entry - (0.80 * risk)

                if bar['low'] <= tp2:
                    trade_pnl = abs(entry - tp2) * point_val
                    outcome = "FULL_WIN"
                    break

                if bar['high'] >= current_sl:
                    if profit_lock_active:
                        outcome = "PROFIT_LOCK_WIN"
                        trade_pnl = (entry - current_sl) * point_val
                    elif be_active:
                        outcome = "BE"
                        trade_pnl = 0.0
                    else:
                        outcome = "LOSS"
                        trade_pnl = -abs(current_sl - entry) * point_val
                    break

        if outcome == "FULL_WIN":
            full_wins += 1
        elif outcome == "PROFIT_LOCK_WIN":
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
        "combo": combo_name,
        "tf": tf_name,
        "lot": lot,
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
    parser = argparse.ArgumentParser(description="Run S20.30 Multi-Strategy Synergy Backtest (Strict Lot 0.01)")
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
        "M30": mt5.TIMEFRAME_M30
    }
    mt5_tf = tf_map.get(args.tf, mt5.TIMEFRAME_M30)

    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=args.days)

    print(f"\n================================================================================")
    print(f" S20.30 MULTI-STRATEGY CONFLUENCE MATRIX (STRICT LOT 0.01)")
    print(f" Symbol: {symbol_gold} | Correlated: {symbol_silver} | TF: {args.tf} | Days: {args.days}")
    print(f"================================================================================")

    gold_rates = mt5.copy_rates_range(symbol_gold, mt5_tf, start_dt, now)
    silver_rates = mt5.copy_rates_range(symbol_silver, mt5_tf, start_dt, now)

    mt5.shutdown()

    if gold_rates is None or len(gold_rates) == 0:
        print("[ERROR] Failed to fetch Gold data")
        return

    print(f"Loaded Gold bars: {len(gold_rates)} | Silver bars: {len(silver_rates) if silver_rates is not None else 0}")
    print("Computing multi-strategy indicators...")
    df = strategy20_30.compute_indicators_df(gold_rates, silver_rates)

    combos = [
        ("combo_baseline_sweep", "Combo A: Pure Liquidity Sweep + Vol (Baseline)"),
        ("combo_sweep_smt", "Combo B: Sweep + Intermarket SMT Divergence"),
        ("combo_sweep_vwap", "Combo C: Sweep + Session Anchored VWAP"),
        ("combo_sweep_rsi_div", "Combo D: Sweep + RSI Divergence"),
        ("combo_grand_synergy", "Combo E: Grand Confluence (Sweep + SMT + VWAP + Vol)")
    ]

    results = []
    print(f"\n{'-'*85}")
    print(f" RUNNING SYNERGY COMPARISON ACROSS {args.days} DAYS AT EXACTLY LOT 0.01...")
    print(f"{'-'*85}")

    for c_key, c_desc in combos:
        res = simulate_synergy_combo(gold_rates, df, combo_name=c_key, tf_name=args.tf)
        results.append(res)
        print(f"\n>>> {c_desc}")
        print(f"    Trades: {res['trades']} | Win Rate: {res['effective_wr']:.1f}%")
        print(f"    Full Wins (4.0R): {res['full_wins']} | Lock Wins (+0.8R): {res['scalp_wins']} | BEs: {res['breakevens']} | Full Losses: {res['full_losses']}")
        print(f"    Net Profit: ${res['net_pnl']:.2f} | PF: {res['pf']:.2f} | MaxDD: ${res['max_dd']:.2f}")
        print(f"    Profitable Months: {res['pos_months']}/{res['tot_months']} ({res['month_wr_pct']:.1f}%)")

    summary_df = pd.DataFrame([
        {
            "Synergy_Combo": r["combo"],
            "TF": r["tf"],
            "Lot": r["lot"],
            "Trades": r["trades"],
            "WinRate%": round(r["effective_wr"], 1),
            "FullWins": r["full_wins"],
            "LockWins": r["scalp_wins"],
            "BEs": r["breakevens"],
            "Losses": r["full_losses"],
            "NetPnL($)": round(r["net_pnl"], 2),
            "PF": round(r["pf"], 2),
            "MaxDD($)": round(r["max_dd"], 2),
            "WinMonths": f"{r['pos_months']}/{r['tot_months']}"
        }
        for r in results
    ])

    out_csv = os.path.join(current_dir, f"S20_30_{args.tf}_synergy_comparison.csv")
    summary_df.to_csv(out_csv, index=False)
    print(f"\nSaved comparison to: {out_csv}")
    print(f"\nSummary Matrix Table:\n{summary_df.to_string(index=False)}")


if __name__ == "__main__":
    main()
