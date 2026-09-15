# -*- coding: utf-8 -*-
"""backtest_s20_19_runner.py — Backtest Runner for S20.19 Sniper Scalper ($10 Target)
Simulates $100 starting account trading Gold (XAUUSD.iux) on M5 / M15.
Tests Lot 0.02, 0.03, and 0.04 to reach $10 target per winning trade.
"""

import argparse
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

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

import strategy20_19


def init_mt5():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()


def run_sniper_backtest(days=60, symbol="XAUUSD.iux", tf_list=None, start_capital=100.0, target_dollar=10.0, max_risk=6.50):
    if tf_list is None:
        tf_list = ["M1", "M5"]

    if not init_mt5():
        print("❌ MT5 Failed to initialize")
        return

    sym_info = mt5.symbol_info(symbol)
    contract_size = sym_info.trade_contract_size if sym_info else 100.0

    print("==========================================================================")
    print(f"  🎯 S20.19 Sniper Scalper ($10/Trade) Backtest Runner")
    print(f"  Initial Account: ${start_capital:.2f} | Target: ${target_dollar:.2f} per Win")
    print(f"  Symbol: {symbol} | Days: {days}")
    print("==========================================================================\n")

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30
    }

    results = []

    for tf_name in tf_list:
        if tf_name not in tf_map:
            continue

        print(f"\n📊 --- Processing Timeframe: {tf_name} ---")
        rates = mt5.copy_rates_range(symbol, tf_map[tf_name], start_time, end_time)
        if rates is None or len(rates) < 100:
            print(f"⚠️ Insufficient data for {tf_name}")
            continue

        print(f"   Loaded {len(rates):,} bars")
        df_master = strategy20_19.compute_indicators_df(rates)

        # Test lot sizes: 0.02 ($5 move needed), 0.03 ($3.33 move needed), 0.04 ($2.50 move needed)
        for lot in [0.02, 0.03, 0.04]:
            dollar_per_dollar_move = contract_size * lot
            points_needed = (target_dollar / dollar_per_dollar_move) * 100.0
            print(f"   Testing Lot: {lot:.2f} (Target dist: {points_needed/100:.2f}$ / {points_needed:.0f} pts) ... ", end="", flush=True)

            trades = 0
            wins = 0
            losses = 0
            be = 0
            equity = start_capital
            peak_equity = start_capital
            max_dd = 0.0
            gross_profit = 0.0
            gross_loss = 0.0

            i = 30
            n_bars = len(rates)

            while i < n_bars - 5:
                res = strategy20_19.evaluate_bar(
                    df_master, i, tf=tf_name, lot=lot, target_dollar=target_dollar, contract_size=contract_size, max_allowed_risk=max_risk
                )
                if not res or res.get("signal") not in ("BUY", "SELL"):
                    i += 1
                    continue

                sig = res["signal"]
                entry = rates[i + 1]['open']  # Fill at next bar open
                target_dist = target_dollar / dollar_per_dollar_move
                risk_dist = res["risk_dollar"] / dollar_per_dollar_move

                if sig == "BUY":
                    tp = round(entry + target_dist, 2)
                    sl = round(entry - risk_dist, 2)
                    be_trigger = entry + (target_dist * 0.40)
                else:
                    tp = round(entry - target_dist, 2)
                    sl = round(entry + risk_dist, 2)
                    be_trigger = entry - (target_dist * 0.40)

                future_bars = rates[i + 1:]
                outcome = None
                exit_price = entry
                be_active = False
                bars_held = 0

                for bar in future_bars:
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
                        if not be_active and bar['high'] >= be_trigger:
                            be_active = True
                            sl = entry  # Lock Breakeven
                    elif sig == "SELL":
                        if bar['high'] >= sl:
                            outcome = "BE" if be_active else "LOSS"
                            exit_price = sl
                            break
                        if bar['low'] <= tp:
                            outcome = "WIN"
                            exit_price = tp
                            break
                        if not be_active and bar['low'] <= be_trigger:
                            be_active = True
                            sl = entry  # Lock Breakeven

                if outcome == "WIN":
                    trades += 1
                    wins += 1
                    profit = abs(exit_price - entry) * dollar_per_dollar_move
                    equity += profit
                    gross_profit += profit
                elif outcome == "LOSS":
                    trades += 1
                    losses += 1
                    loss = abs(entry - exit_price) * dollar_per_dollar_move
                    equity -= loss
                    gross_loss += loss
                elif outcome == "BE":
                    trades += 1
                    be += 1

                if equity > peak_equity:
                    peak_equity = equity
                dd = peak_equity - equity
                if dd > max_dd:
                    max_dd = dd

                # Check if account blew up
                if equity <= 10.0:
                    print(f"💀 Account blown at trade {trades}!")
                    break

                i += max(1, bars_held)

            decided = wins + losses
            wr = (wins / decided * 100.0) if decided > 0 else 0.0
            pf = (gross_profit / gross_loss) if gross_loss > 0 else 99.0
            net_profit = equity - start_capital
            roi_pct = (net_profit / start_capital) * 100.0

            print(f"Trades: {trades:3d} | WR: {wr:4.1f}% | Net: ${net_profit:+7.2f} (ROI: {roi_pct:+6.1f}%) | PF: {pf:4.2f} | MaxDD: ${max_dd:5.2f} | Final: ${equity:6.2f}")

            results.append({
                "TF": tf_name,
                "Lot": lot,
                "Trades": trades,
                "Wins": wins,
                "Losses": losses,
                "BE": be,
                "WinRate%": round(wr, 1),
                "StartCap($)": start_capital,
                "FinalEquity($)": round(equity, 2),
                "NetProfit($)": round(net_profit, 2),
                "ROI(%)": round(roi_pct, 1),
                "ProfitFactor": round(pf, 2),
                "MaxDrawdown($)": round(max_dd, 2)
            })

    mt5.shutdown()

    if results:
        res_df = pd.DataFrame(results)
        csv_path = os.path.join(current_dir, "S20_19_backtest_summary.csv")
        res_df.to_csv(csv_path, index=False)
        print(f"\n✅ Summary exported to: {csv_path}")
        print("\n" + "=" * 95)
        print(f"🏆 S20.19 SNIPER SCALPER SUMMARY TABLE (Start Capital: ${start_capital:.0f})")
        print("=" * 95)
        print(res_df.to_string(index=False))
        print("=" * 95)
        return res_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="S20.19 Sniper Scalper Runner")
    parser.add_argument("--days", type=int, default=180, help="Days to backtest")
    parser.add_argument("--capital", type=float, default=100.0, help="Starting capital ($)")
    parser.add_argument("--target", type=float, default=10.0, help="Target dollar per win ($)")
    parser.add_argument("--tf", type=str, default="M5,M15", help="Timeframes comma-separated")

    args = parser.parse_args()
    tf_list = [x.strip() for x in args.tf.split(",") if x.strip()]
    run_sniper_backtest(days=args.days, tf_list=tf_list, start_capital=args.capital, target_dollar=args.target)
