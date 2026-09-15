# -*- coding: utf-8 -*-
"""backtest_s20_20_runner.py — Backtest Runner comparing:
1. Engine A: Asymmetric R:R (1:7+)
2. Engine B: High Winrate Asian Mean Reversion
Tested on historical MT5 Gold (XAUUSD.iux) with Lot 0.01.
"""

import argparse
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
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

import strategy20_20


def init_mt5():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()


def simulate_engine(rates, df, engine_type="Asymmetric_RR", min_rr=7.0, lot=0.01, point_val=1.0):
    trades = 0; wins = 0; losses = 0; be = 0
    gross_profit = 0.0; gross_loss = 0.0; pnl = 0.0
    max_pnl = 0.0; max_dd = 0.0
    win_rrs = []

    i = 65
    n = len(rates)
    while i < n - 10:
        if engine_type == "Asymmetric_RR":
            res = strategy20_20.evaluate_asymmetric_rr(df, i, min_rr=min_rr)
        else:
            res = strategy20_20.evaluate_asian_mean_reversion(df, i)

        if not res:
            i += 1
            continue

        sig = res["signal"]
        entry = rates[i + 1]['open']  # next bar open fill
        sl = res["sl"]
        tp = res["tp"]
        be_trig = res["be_trigger"]
        planned_risk = abs(entry - sl)
        planned_reward = abs(tp - entry)
        actual_rr = planned_reward / (planned_risk + 1e-5)

        future = rates[i + 1:]
        outcome = None
        exit_price = entry
        be_active = False
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
            trades += 1; wins += 1
            diff = abs(exit_price - entry) * point_val
            gross_profit += diff; pnl += diff
            win_rrs.append(actual_rr)
        elif outcome == "LOSS":
            trades += 1; losses += 1
            diff = abs(entry - exit_price) * point_val
            gross_loss += diff; pnl -= diff
        elif outcome == "BE":
            trades += 1; be += 1

        if pnl > max_pnl: max_pnl = pnl
        dd = max_pnl - pnl
        if dd > max_dd: max_dd = dd

        i += max(1, bars_held)

    decided = wins + losses
    wr = (wins / decided * 100.0) if decided > 0 else 0.0
    all_wr = (wins / trades * 100.0) if trades > 0 else 0.0
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
    avg_win_rr = np.mean(win_rrs) if win_rrs else 0.0

    return {
        "trades": trades, "wins": wins, "losses": losses, "be": be,
        "wr": wr, "all_wr": all_wr, "pnl": pnl, "pf": pf, "max_dd": max_dd,
        "gross_profit": gross_profit, "gross_loss": gross_loss, "avg_win_rr": avg_win_rr
    }


def main():
    if not init_mt5():
        print("❌ MT5 initialize failed")
        return

    symbol = "XAUUSD.iux"
    days = 180
    lot = 0.01
    contract_size = 100.0
    point_val = contract_size * lot

    print("=========================================================================")
    print(f"  🏛️ S20.20 Institutional Battle: Asymmetric R:R (1:7+) vs Asian High-WR")
    print(f"  Symbol: {symbol} | Lot Size: {lot} | Backtest Period: {days} Days")
    print("=========================================================================\n")

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    results = []

    for tf_name in ["M5", "M15"]:
        tf_code = mt5.TIMEFRAME_M5 if tf_name == "M5" else mt5.TIMEFRAME_M15
        print(f"\n📊 --- Processing Timeframe: {tf_name} ---")
        rates = mt5.copy_rates_range(symbol, tf_code, start_time, end_time)
        if rates is None or len(rates) < 100:
            print(f"⚠️ Insufficient data for {tf_name}")
            continue

        print(f"   Loaded {len(rates):,} bars")
        df = strategy20_20.compute_indicators_df(rates)

        # 1. Test Asymmetric R:R 1:5, 1:7
        for min_rr in [5.0, 7.0]:
            eng_name = f"Asymmetric_RR_{min_rr:.0f}R"
            print(f"   Testing {eng_name} ... ", end="", flush=True)
            res = simulate_engine(rates, df, engine_type="Asymmetric_RR", min_rr=min_rr, lot=lot, point_val=point_val)
            print(f"Trades: {res['trades']:3d} | WR: {res['wr']:4.1f}% | Net: ${res['pnl']:+7.2f} | PF: {res['pf']:4.2f} | DD: ${res['max_dd']:5.2f} | Avg RR: {res['avg_win_rr']:.1f}")
            results.append({
                "TF": tf_name,
                "Strategy": f"Asymmetric RR (1:{min_rr:.0f}+)",
                "Trades": res["trades"],
                "Wins": res["wins"],
                "Losses": res["losses"],
                "BE": res["be"],
                "WinRate%": round(res["wr"], 1),
                "AvgWinRR": round(res["avg_win_rr"], 1),
                "NetProfit($)": round(res["pnl"], 2),
                "ProfitFactor": round(res["pf"], 2),
                "MaxDD($)": round(res["max_dd"], 2)
            })

        # 2. Test Asian Session Mean Reversion
        eng_name = "Asian_Mean_Reversion"
        print(f"   Testing {eng_name} ... ", end="", flush=True)
        res = simulate_engine(rates, df, engine_type="Asian_Mean_Reversion", lot=lot, point_val=point_val)
        print(f"Trades: {res['trades']:3d} | WR: {res['wr']:4.1f}% | Net: ${res['pnl']:+7.2f} | PF: {res['pf']:4.2f} | DD: ${res['max_dd']:5.2f} | Avg RR: {res['avg_win_rr']:.1f}")
        results.append({
            "TF": tf_name,
            "Strategy": "Asian Mean Reversion (High WR)",
            "Trades": res["trades"],
            "Wins": res["wins"],
            "Losses": res["losses"],
            "BE": res["be"],
            "WinRate%": round(res["wr"], 1),
            "AvgWinRR": round(res["avg_win_rr"], 1),
            "NetProfit($)": round(res["pnl"], 2),
            "ProfitFactor": round(res["pf"], 2),
            "MaxDD($)": round(res["max_dd"], 2)
        })

    mt5.shutdown()

    if results:
        res_df = pd.DataFrame(results)
        csv_path = os.path.join(current_dir, "S20_20_comparison_summary.csv")
        res_df.to_csv(csv_path, index=False)
        print(f"\n✅ Results exported to: {csv_path}")
        print("\n" + "=" * 105)
        print("🏆 S20.20 INSTITUTIONAL COMPARISON: ASYMMETRIC R:R vs HIGH-WINRATE ASIAN REVERSION")
        print("=" * 105)
        print(res_df.to_string(index=False))
        print("=" * 105)


if __name__ == "__main__":
    main()
