# -*- coding: utf-8 -*-
"""backtest_s20_23_runner.py — 365-Day Backtest & Monthly PnL for S20.23 Hybrid Engine:
Simulates Dual-Target Execution:
- 50% Lot closed at TP1 (Fast Scalp 1.8R) -> Locks in initial cashflow
- SL shifted to Breakeven (+0.2R) on runner
- Remaining 50% Lot trailing to TP2 (Session Runner 3.5R+)
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

import strategy20_23


def init_mt5():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()


def run_hybrid_backtest(days=365, symbol="XAUUSD.iux", total_lot=0.02, tf_name="M30"):
    if not init_mt5():
        print("❌ MT5 Failed to initialize")
        return

    sym_info = mt5.symbol_info(symbol)
    contract_size = sym_info.trade_contract_size if sym_info else 100.0
    # Split 50% for Scalp and 50% for Runner
    scalp_lot = total_lot / 2.0
    runner_lot = total_lot / 2.0
    point_val_scalp = contract_size * scalp_lot
    point_val_runner = contract_size * runner_lot

    print("=========================================================================")
    print(f"  🎯 S20.23 Hybrid Liquidity Trap & Scalp-Runner 365-Day Tear Sheet")
    print(f"  Symbol: {symbol} | TF: {tf_name} | Total Lot: {total_lot} (Scalp: {scalp_lot} + Runner: {runner_lot})")
    print("=========================================================================\n")

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    tf_code = mt5.TIMEFRAME_M30 if tf_name == "M30" else mt5.TIMEFRAME_M15
    rates = mt5.copy_rates_range(symbol, tf_code, start_time, end_time)
    if rates is None or len(rates) < 100:
        print("❌ Insufficient rates data")
        mt5.shutdown()
        return

    print(f"Loaded {len(rates):,} bars from {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}")
    df = strategy20_23.compute_indicators_df(rates)

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
    n = len(rates)

    while i < n - 5:
        res = strategy20_23.evaluate_hybrid_setup(df, i, tf=tf_name)
        if not res:
            i += 1
            continue

        sig = res["signal"]
        entry = res["entry"]
        sl = res["sl"]
        tp1 = res["tp_scalp"]
        tp2 = res["tp_runner"]
        be_trig = entry + ((tp1 - entry) * 0.40) if sig == "BUY" else entry - ((entry - tp1) * 0.40)

        # Check limit fill within 5 bars
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
                # Check BE activation before TP1
                if not be_active and bar['high'] >= be_trig:
                    be_active = True
                    runner_sl = entry

                # Check TP1
                if not tp1_hit and bar['high'] >= tp1:
                    tp1_hit = True
                    be_active = True
                    runner_sl = entry + 0.30  # lock breakeven + slight profit buffer
                    trade_pnl += abs(tp1 - entry) * point_val_scalp

                # Check TP2 (Runner)
                if tp1_hit and not tp2_hit and bar['high'] >= tp2:
                    tp2_hit = True
                    trade_pnl += abs(tp2 - entry) * point_val_runner
                    outcome = "FULL_WIN"
                    break

                # Check SL
                if bar['low'] <= runner_sl:
                    if not tp1_hit:
                        # Full stopout
                        if be_active:
                            outcome = "BE"
                            trade_pnl = 0.0
                        else:
                            outcome = "LOSS"
                            trade_pnl = -abs(entry - runner_sl) * (point_val_scalp + point_val_runner)
                    else:
                        # TP1 was secured, runner stopped at BE
                        outcome = "SCALP_WIN"
                        # Runner exited at BE (+0.30)
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

        trades += 1
        if outcome == "FULL_WIN":
            full_wins += 1
        elif outcome == "SCALP_WIN":
            scalp_wins += 1
        elif outcome == "LOSS":
            full_losses += 1
        elif outcome == "BE":
            breakevens += 1

        pnl += trade_pnl
        if pnl > max_pnl: max_pnl = pnl
        dd = max_pnl - pnl
        if dd > max_dd: max_dd = dd

        trade_records.append({
            "time": entry_time,
            "month": month_key,
            "outcome": outcome,
            "pnl": trade_pnl
        })

        i += max(1, bars_held)

    mt5.shutdown()

    # Total Wins = Full Wins + Scalp Wins
    total_wins = full_wins + scalp_wins
    decided = total_wins + full_losses
    wr = (total_wins / decided * 100.0) if decided > 0 else 0.0

    # Monthly Breakdown
    trades_df = pd.DataFrame(trade_records)
    monthly_rows = []
    cum_equity = 0.0

    for m in sorted(trades_df['month'].unique()):
        m_df = trades_df[trades_df['month'] == m]
        m_trades = len(m_df)
        m_wins = len(m_df[m_df['outcome'].isin(["FULL_WIN", "SCALP_WIN"])])
        m_losses = len(m_df[m_df['outcome'] == "LOSS"])
        m_be = len(m_df[m_df['outcome'] == "BE"])
        m_pnl = m_df['pnl'].sum()
        cum_equity += m_pnl
        m_wr = (m_wins / (m_wins + m_losses) * 100.0) if (m_wins + m_losses) > 0 else 0.0

        gross_w = m_df[m_df['pnl'] > 0]['pnl'].sum()
        gross_l = abs(m_df[m_df['pnl'] < 0]['pnl'].sum())
        m_pf = (gross_w / gross_l) if gross_l > 0 else (99.0 if gross_w > 0 else 0.0)

        monthly_rows.append({
            "Month": m,
            "Trades": m_trades,
            "Wins": m_wins,
            "Losses": m_losses,
            "BE": m_be,
            "WinRate%": round(m_wr, 1),
            "NetPnL($)": round(m_pnl, 2),
            "ProfitFactor": round(m_pf, 2),
            "CumProfit($)": round(cum_equity, 2)
        })

    m_report_df = pd.DataFrame(monthly_rows)
    csv_path = os.path.join(current_dir, f"S20_23_{tf_name}_monthly_breakdown.csv")
    m_report_df.to_csv(csv_path, index=False)

    gross_profit_all = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
    gross_loss_all = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
    pf_all = (gross_profit_all / gross_loss_all) if gross_loss_all > 0 else 99.0

    print("=" * 100)
    print(f"🏆 S20.23 HYBRID DUAL-EXIT MONTH-BY-MONTH TEAR SHEET ({tf_name} | 365 Days)")
    print("=" * 100)
    print(m_report_df.to_string(index=False))
    print("=" * 100)

    pos_months = len(m_report_df[m_report_df['NetPnL($)'] > 0])
    tot_months = len(m_report_df)
    print(f"\n📊 Total Trades: {trades} | Full Wins (Both TP1&TP2): {full_wins} | Scalp Wins (TP1 Hit): {scalp_wins}")
    print(f"🛡️ Losses: {full_losses} | Breakeven: {breakevens}")
    print(f"🎯 Overall Win Rate: {wr:.1f}% (Counting Secured Scalp Wins)")
    print(f"💰 Total Net Profit (Total Lot {total_lot}): ${pnl:,.2f}")
    print(f"⚡ Profit Factor: {pf_all:.2f} | Max Drawdown: ${max_dd:,.2f}")
    print(f"🌟 Monthly Win Rate: {pos_months}/{tot_months} months ({(pos_months/tot_months)*100:.1f}%)")
    print(f"📁 Detailed CSV saved to: {csv_path}\n")

    return m_report_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="S20.23 Hybrid Backtest Runner")
    parser.add_argument("--days", type=int, default=365, help="Days to backtest")
    parser.add_argument("--lot", type=float, default=0.02, help="Total Lot size (default 0.02 = 0.01 scalp + 0.01 runner)")
    parser.add_argument("--tf", type=str, default="M30", help="Timeframe (M30 or M15)")
    args = parser.parse_args()
    run_hybrid_backtest(days=args.days, total_lot=args.lot, tf_name=args.tf)
