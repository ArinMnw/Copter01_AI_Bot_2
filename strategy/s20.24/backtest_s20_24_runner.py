# -*- coding: utf-8 -*-
"""backtest_s20_24_runner.py — 365-Day Backtest & Monthly Analysis for S20.24:
1. Engine A: Wyckoff VSA (Stopping Volume + No Supply/Demand Confirmation)
2. Engine B: London Close Reversal (Fixing Window 22:00-23:30 BKK)
Tested on historical MT5 Gold (XAUUSD.iux) over 365 days.
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

import strategy20_24


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
        if engine_name == "Wyckoff_VSA":
            res = strategy20_24.evaluate_wyckoff_vsa(df, i)
        elif engine_name == "London_Close_Reversal":
            res = strategy20_24.evaluate_london_close_reversal(df, i)
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
    days = 365
    lot = 0.01
    contract_size = 100.0
    point_val = contract_size * lot

    print("=========================================================================")
    print(f"  🏛️ S20.24 Wyckoff VSA & London Close Reversal 365-Day Backtest")
    print(f"  Symbol: {symbol} | Lot Size: {lot} | Backtest Period: {days} Days")
    print("=========================================================================\n")

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    results = []
    monthly_all = {}

    for tf_name in ["M15", "M30"]:
        tf_code = mt5.TIMEFRAME_M15 if tf_name == "M15" else mt5.TIMEFRAME_M30
        print(f"\n📊 --- Processing Timeframe: {tf_name} ---")
        rates = mt5.copy_rates_range(symbol, tf_code, start_time, end_time)
        if rates is None or len(rates) < 100:
            print(f"⚠️ Insufficient rates data for {tf_name}")
            continue

        print(f"   Loaded {len(rates):,} bars")
        df = strategy20_24.compute_indicators_df(rates)

        for eng in ["Wyckoff_VSA", "London_Close_Reversal"]:
            print(f"   Testing {eng:22s} ... ", end="", flush=True)
            res = simulate_engine(rates, df, eng, lot=lot, point_val=point_val)
            print(f"Trades: {res['trades']:3d} | WR: {res['wr']:4.1f}% | Net: ${res['pnl']:+7.2f} | PF: {res['pf']:4.2f} | DD: ${res['max_dd']:5.2f}")
            results.append({
                "TF": tf_name,
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
            monthly_all[f"{tf_name}_{eng}"] = res["monthly"]

    mt5.shutdown()

    # Print Summary Table
    sum_df = pd.DataFrame(results)
    print("\n" + "=" * 90)
    print("🏆 S20.24 DUAL ENGINES 365-DAY SUMMARY (Lot 0.01)")
    print("=" * 90)
    print(sum_df.to_string(index=False))
    print("=" * 90)

    # Monthly Breakdown Table
    months = sorted(list(set(m for eng_dict in monthly_all.values() for m in eng_dict.keys())))
    m_rows = []
    for m in months:
        row = {"Month": m}
        for k in monthly_all.keys():
            e_data = monthly_all[k].get(m, {"pnl": 0.0})
            row[f"{k}_PnL($)"] = e_data.get("pnl", 0.0)
        m_rows.append(row)

    if m_rows:
        m_comp_df = pd.DataFrame(m_rows)
        csv_path = os.path.join(current_dir, "S20_24_monthly_breakdown.csv")
        m_comp_df.to_csv(csv_path, index=False)
        print(f"\n📅 S20.24 MONTH-BY-MONTH PnL BREAKDOWN (365 Days):")
        print("=" * 90)
        print(m_comp_df.to_string(index=False))
        print("=" * 90)
        print(f"📁 Detailed CSV saved to: {csv_path}\n")


if __name__ == "__main__":
    main()
