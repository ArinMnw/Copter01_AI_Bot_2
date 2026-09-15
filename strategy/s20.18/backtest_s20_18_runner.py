# -*- coding: utf-8 -*-
"""backtest_s20_18_runner.py — 365-Day Backtest Runner for S20.18 (Order Flow Delta & Absorption)
Simulates trade lifecycle on historical MT5 rates with Lot 0.01 (XAUUSD.iux).
Includes Breakeven Management, Profit Factor, Drawdown, and Winrate calculations.
"""

import argparse
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import os
import sys

# Append directories
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if current_dir not in sys.path:
    sys.path.append(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

import strategy20_18

BKK = timezone(timedelta(hours=7))


def init_mt5():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()


def run_backtest(days=365, tf_list=None, symbol="XAUUSD.iux", lot=0.01, rr=1.8, be_ratio=0.4):
    if tf_list is None:
        tf_list = ["M5", "M15", "M30", "H1", "H4"]

    if not init_mt5():
        print("❌ MT5 initialize failed!")
        return

    # Check symbol specs
    sym_info = mt5.symbol_info(symbol)
    contract_size = sym_info.trade_contract_size if sym_info else 100.0
    # For Gold 0.01 lot: $1 price move = $1.00 USD
    point_value_per_dollar_move = contract_size * lot

    print(f"=========================================================================")
    print(f"  🏛️ S20.18 Institutional Order Flow & Absorption Backtest Runner")
    print(f"  Symbol: {symbol} | Lot Size: {lot} | Days: {days} | R:R: {rr}R | BE: {be_ratio*100:.0f}%")
    print(f"=========================================================================\n")

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1
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

        print(f"   Loaded {len(rates):,} bars (~{days} days)")
        df_master = strategy20_18.compute_indicators_df(rates)

        for entry_mode in ["MARKET", "RETEST"]:
            print(f"   Testing Mode: {entry_mode:6s} ... ", end="", flush=True)

            trades = 0
            wins = 0
            losses = 0
            be = 0
            gross_profit = 0.0
            gross_loss = 0.0
            pnl = 0.0
            max_pnl = 0.0
            max_dd = 0.0
            trade_pnls = []

            i = 30
            n_bars = len(rates)
            while i < n_bars - 5:
                res = strategy20_18.evaluate_bar(df_master, i, tf=tf_name, entry_mode=entry_mode, rr_ratio=rr)
                if not res or res.get("signal") not in ("BUY", "SELL"):
                    i += 1
                    continue

                sig = res["signal"]
                entry = res["entry"]
                sl = res["sl"]
                tp = res["tp"]

                # Check execution on future bars
                future_rates = rates[i + 1:]
                filled = False
                fill_bar_idx = 0

                if entry_mode == "MARKET":
                    filled = True
                    # Fill at next bar open
                    entry = future_rates[0]['open']
                    # Recalculate SL and TP based on actual fill
                    risk = abs(entry - sl)
                    if sig == "BUY":
                        tp = entry + (risk * rr)
                    else:
                        tp = entry - (risk * rr)
                else:
                    # RETEST limit order: wait for price to touch entry within 5 bars
                    for f_idx, f_bar in enumerate(future_rates[:5]):
                        if sig == "BUY" and f_bar['low'] <= entry:
                            filled = True
                            fill_bar_idx = f_idx
                            break
                        elif sig == "SELL" and f_bar['high'] >= entry:
                            filled = True
                            fill_bar_idx = f_idx
                            break

                if not filled:
                    i += 1
                    continue

                # Trade is active, simulate outcome
                active_future = future_rates[fill_bar_idx:]
                be_trigger = entry + ((tp - entry) * be_ratio) if sig == "BUY" else entry - ((entry - tp) * be_ratio)
                be_active = False
                outcome = None
                exit_price = entry
                bars_held = 0

                for bar in active_future:
                    bars_held += 1
                    if sig == "BUY":
                        # Check SL
                        if bar['low'] <= sl:
                            outcome = "BE" if be_active else "LOSS"
                            exit_price = sl
                            break
                        # Check TP
                        if bar['high'] >= tp:
                            outcome = "WIN"
                            exit_price = tp
                            break
                        # Check Breakeven activation
                        if not be_active and bar['high'] >= be_trigger:
                            be_active = True
                            sl = entry  # Move SL to breakeven
                    elif sig == "SELL":
                        # Check SL
                        if bar['high'] >= sl:
                            outcome = "BE" if be_active else "LOSS"
                            exit_price = sl
                            break
                        # Check TP
                        if bar['low'] <= tp:
                            outcome = "WIN"
                            exit_price = tp
                            break
                        # Check Breakeven activation
                        if not be_active and bar['low'] <= be_trigger:
                            be_active = True
                            sl = entry  # Move SL to breakeven

                if outcome == "WIN":
                    trades += 1
                    wins += 1
                    trade_profit = abs(exit_price - entry) * point_value_per_dollar_move
                    gross_profit += trade_profit
                    pnl += trade_profit
                    trade_pnls.append(trade_profit)
                elif outcome == "LOSS":
                    trades += 1
                    losses += 1
                    trade_loss = abs(entry - exit_price) * point_value_per_dollar_move
                    gross_loss += trade_loss
                    pnl -= trade_loss
                    trade_pnls.append(-trade_loss)
                elif outcome == "BE":
                    trades += 1
                    be += 1
                    trade_pnls.append(0.0)

                if pnl > max_pnl:
                    max_pnl = pnl
                dd = max_pnl - pnl
                if dd > max_dd:
                    max_dd = dd

                # Fast forward past the trade bars to avoid overlapping on same move
                i += max(1, bars_held)

            decided = wins + losses
            winrate = (wins / decided * 100.0) if decided > 0 else 0.0
            all_winrate = (wins / trades * 100.0) if trades > 0 else 0.0
            pf = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
            avg_pnl = (pnl / trades) if trades > 0 else 0.0

            print(f"Trades: {trades:3d} | WR (W/L): {winrate:5.1f}% | Net PnL: ${pnl:+8.2f} | PF: {pf:4.2f} | MaxDD: ${max_dd:6.2f}")

            results.append({
                "TF": tf_name,
                "Mode": entry_mode,
                "Trades": trades,
                "Wins": wins,
                "Losses": losses,
                "BE": be,
                "WinRate(W/L)%": round(winrate, 1),
                "TotalWinRate%": round(all_winrate, 1),
                "NetProfit($)": round(pnl, 2),
                "GrossProfit($)": round(gross_profit, 2),
                "GrossLoss($)": round(gross_loss, 2),
                "ProfitFactor": round(pf, 2),
                "MaxDrawdown($)": round(max_dd, 2),
                "AvgTrade($)": round(avg_pnl, 2)
            })

    mt5.shutdown()

    if results:
        res_df = pd.DataFrame(results)
        csv_path = os.path.join(current_dir, "S20_18_backtest_summary.csv")
        res_df.to_csv(csv_path, index=False)
        print(f"\n✅ Results successfully exported to: {csv_path}")
        print("\n" + "=" * 90)
        print("🏆 S20.18 BACKTEST SUMMARY TABLE (Lot 0.01 | 365 Days)")
        print("=" * 90)
        print(res_df.to_string(index=False))
        print("=" * 90)
        return res_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="S20.18 Backtest Runner")
    parser.add_argument("--days", type=int, default=365, help="Number of days to backtest")
    parser.add_argument("--tf", type=str, default="M5,M15,M30,H1,H4", help="Timeframes comma-separated")
    parser.add_argument("--lot", type=float, default=0.01, help="Lot size (default 0.01)")
    parser.add_argument("--rr", type=float, default=1.8, help="Risk Reward ratio (default 1.8)")

    args = parser.parse_args()
    tf_list = [x.strip() for x in args.tf.split(",") if x.strip()]
    run_backtest(days=args.days, tf_list=tf_list, lot=args.lot, rr=args.rr)
