# -*- coding: utf-8 -*-
"""backtest_s20_21_runner.py — 365-Day Backtest & Monthly Tear Sheets for S20.21 Triple Engines:
1. SMT Divergence (Gold vs Silver)
2. Judas Swing (London / NY Open Trap)
3. Breaker Block & Mitigation Flow
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

import strategy20_21


def init_mt5():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()


def simulate_engine(rates, df, engine_name, lot=0.01, point_val=1.0):
    trades = 0; wins = 0; losses = 0; be = 0
    gross_profit = 0.0; gross_loss = 0.0; pnl = 0.0
    max_pnl = 0.0; max_dd = 0.0
    monthly_records = []

    i = 30
    n = len(rates)
    while i < n - 5:
        if engine_name == "SMT_Divergence":
            res = strategy20_21.evaluate_smt_divergence(df, i)
        elif engine_name == "Judas_Swing":
            res = strategy20_21.evaluate_judas_swing(df, i)
        elif engine_name == "Breaker_Block":
            res = strategy20_21.evaluate_breaker_block(df, i)
        else:
            res = None

        if not res:
            i += 1
            continue

        sig = res["signal"]
        entry = rates[i + 1]['open']
        sl = res["sl"]
        tp = res["tp"]
        be_ratio = res.get("be_ratio", 0.40)
        risk = abs(entry - sl)
        target = abs(tp - entry)

        entry_time = datetime.fromtimestamp(rates[i + 1]['time'], tz=timezone.utc)
        month_key = entry_time.strftime("%Y-%m")

        future = rates[i + 1:]
        be_trig = entry + (target * be_ratio) if sig == "BUY" else entry - (target * be_ratio)
        be_active = False
        outcome = None
        exit_price = entry
        bars_held = 0

        for bar in future:
            bars_held += 1
            if sig == "BUY":
                if bar['low'] <= sl:
                    outcome = "BE" if be_active else "LOSS"
                    exit_price = sl
                    break
                if bar['high'] >= tp:
                    outcome = "WIN"
                    exit_price = tp
                    break
                if not be_active and bar['high'] >= be_trig:
                    be_active = True
                    sl = entry
            elif sig == "SELL":
                if bar['high'] >= sl:
                    outcome = "BE" if be_active else "LOSS"
                    exit_price = sl
                    break
                if bar['low'] <= tp:
                    outcome = "WIN"
                    exit_price = tp
                    break
                if not be_active and bar['low'] <= be_trig:
                    be_active = True
                    sl = entry

        if outcome == "WIN":
            trade_pnl = abs(exit_price - entry) * point_val
            trades += 1; wins += 1
            gross_profit += trade_pnl
            pnl += trade_pnl
        elif outcome == "LOSS":
            trade_pnl = -abs(entry - exit_price) * point_val
            trades += 1; losses += 1
            gross_loss += abs(trade_pnl)
            pnl += trade_pnl
        elif outcome == "BE":
            trade_pnl = 0.0
            trades += 1; be += 1

        if pnl > max_pnl: max_pnl = pnl
        dd = max_pnl - pnl
        if dd > max_dd: max_dd = dd

        monthly_records.append({
            "month": month_key,
            "outcome": outcome,
            "pnl": trade_pnl
        })

        i += max(1, bars_held)

    decided = wins + losses
    wr = (wins / decided * 100.0) if decided > 0 else 0.0
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

    # Aggregate monthly
    m_summary = {}
    if monthly_records:
        m_df = pd.DataFrame(monthly_records)
        for m, grp in m_df.groupby('month'):
            m_summary[m] = {
                "trades": len(grp),
                "wins": len(grp[grp['outcome'] == "WIN"]),
                "losses": len(grp[grp['outcome'] == "LOSS"]),
                "be": len(grp[grp['outcome'] == "BE"]),
                "pnl": round(grp['pnl'].sum(), 2)
            }

    return {
        "engine": engine_name,
        "trades": trades, "wins": wins, "losses": losses, "be": be,
        "wr": wr, "pnl": pnl, "pf": pf, "max_dd": max_dd,
        "monthly": m_summary
    }


def main():
    if not init_mt5():
        print("❌ MT5 initialize failed")
        return

    symbol = "XAUUSD.iux"
    corr_symbol = "XAGUSD.iux"
    days = 365
    lot = 0.01
    contract_size = 100.0
    point_val = contract_size * lot
    tf_name = "M15"
    tf_code = mt5.TIMEFRAME_M15

    print("=========================================================================")
    print(f"  🏛️ S20.21 Triple Institutional Matrix 365-Day Backtest")
    print(f"  Symbol: {symbol} & {corr_symbol} | TF: {tf_name} | Lot: {lot} | Days: {days}")
    print("=========================================================================\n")

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    rates_gold = mt5.copy_rates_range(symbol, tf_code, start_time, end_time)
    rates_silver = mt5.copy_rates_range(corr_symbol, tf_code, start_time, end_time)
    if rates_gold is None or len(rates_gold) < 100:
        print("❌ Insufficient rates data")
        mt5.shutdown()
        return

    print(f"Loaded {len(rates_gold):,} bars for Gold ({len(rates_silver):,} bars for Silver)")
    df = strategy20_21.compute_indicators_df(rates_gold, rates_silver)

    engines = ["SMT_Divergence", "Judas_Swing", "Breaker_Block"]
    summary_list = []
    monthly_all = {}

    for eng in engines:
        print(f"Running Engine: {eng:18s} ... ", end="", flush=True)
        res = simulate_engine(rates_gold, df, eng, lot=lot, point_val=point_val)
        print(f"Trades: {res['trades']:3d} | WR: {res['wr']:4.1f}% | Net: ${res['pnl']:+7.2f} | PF: {res['pf']:4.2f} | DD: ${res['max_dd']:5.2f}")
        summary_list.append({
            "Engine": eng,
            "Trades": res["trades"],
            "Wins": res["wins"],
            "Losses": res["losses"],
            "BE": res["be"],
            "WinRate%": round(res["wr"], 1),
            "NetProfit($)": round(res["pnl"], 2),
            "ProfitFactor": round(res["pf"], 2),
            "MaxDD($)": round(res["max_dd"], 2)
        })
        monthly_all[eng] = res["monthly"]

    mt5.shutdown()

    # Print Comparison Table
    sum_df = pd.DataFrame(summary_list)
    print("\n" + "=" * 90)
    print("🏆 S20.21 TRIPLE ENGINE 365-DAY OVERALL SUMMARY (Lot 0.01)")
    print("=" * 90)
    print(sum_df.to_string(index=False))
    print("=" * 90)

    # Monthly Breakdown Table for All 3
    months = sorted(list(set(m for eng_dict in monthly_all.values() for m in eng_dict.keys())))
    m_rows = []
    for m in months:
        row = {"Month": m}
        for eng in engines:
            e_data = monthly_all[eng].get(m, {"pnl": 0.0, "trades": 0, "wins": 0, "losses": 0})
            row[f"{eng}_PnL($)"] = e_data.get("pnl", 0.0)
            row[f"{eng}_Trades"] = e_data.get("trades", 0)
        m_rows.append(row)

    if m_rows:
        m_comp_df = pd.DataFrame(m_rows)
        csv_path = os.path.join(current_dir, "S20_21_monthly_breakdown.csv")
        m_comp_df.to_csv(csv_path, index=False)
        print(f"\n📅 S20.21 MONTH-BY-MONTH PnL COMPARISON (365 Days):")
        print("=" * 90)
        # Select PnL columns for clean view
        pnl_cols = ["Month"] + [f"{eng}_PnL($)" for eng in engines]
        print(m_comp_df[pnl_cols].to_string(index=False))
        print("=" * 90)
        print(f"📁 Detailed CSV saved to: {csv_path}\n")


if __name__ == "__main__":
    main()
