# -*- coding: utf-8 -*-
"""monthly_analysis.py — 365-Day Monthly Breakdown for S20.18 (M30 & M15 Fibo Retest 38.2%)
Calculates Month-by-Month: Trades, Wins, Losses, BE, WinRate%, Net PnL ($), and Cumulative Equity.
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


def run_monthly_backtest(days=365, symbol="XAUUSD.iux", lot=0.01, tf_name="M30"):
    if not init_mt5():
        print("❌ MT5 Failed to initialize")
        return

    sym_info = mt5.symbol_info(symbol)
    contract_size = sym_info.trade_contract_size if sym_info else 100.0
    point_val = contract_size * lot

    print("=========================================================================")
    print(f"  📅 S20.18 365-Day Monthly Performance Tear Sheet")
    print(f"  Symbol: {symbol} | Timeframe: {tf_name} | Lot Size: {lot} | Days: {days}")
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
    df = strategy20_18.compute_indicators_df(rates)

    # Use Champion Settings: Fibo Retest 38.2%, RR 1.8, BE 40%
    retest_depth = 0.382
    rr = 1.8
    be_ratio = 0.40
    min_vol = 1.25
    min_wick = 0.38

    trade_records = []
    i = 30
    n = len(rates)

    while i < n - 5:
        cur = df.iloc[i]
        if pd.isna(cur['atr']) or pd.isna(cur['vol_ma20']):
            i += 1
            continue

        atr = cur['atr']
        if atr <= 0.05 or cur['range'] < 0.45 * atr or cur['hour'] in (23, 0) or cur['vol_ratio'] < min_vol:
            i += 1
            continue

        sig = None
        # BUY
        swept_low = (cur['low'] <= cur['swing_low_10']) or (cur['low'] <= df.iloc[idx-5:idx]['low'].min() if (idx:=i) else False)
        has_wick_buy = (cur['lower_wick_pct'] >= min_wick) or (cur['lower_wick'] >= 1.1 * cur['body'])
        closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
        if swept_low and has_wick_buy and closed_high and cur['rsi'] <= 68.0:
            sig = "BUY"
            sl_buf = max(0.20 * atr, 0.25)
            sl = round(cur['low'] - sl_buf, 2)
            entry = round(cur['low'] + (retest_depth * cur['lower_wick']), 2)
            risk = entry - sl
            if risk > 0:
                tp = round(entry + (risk * rr), 2)
            else:
                sig = None

        # SELL
        if not sig:
            swept_high = (cur['high'] >= cur['swing_high_10']) or (cur['high'] >= df.iloc[idx-5:idx]['high'].max() if (idx:=i) else False)
            has_wick_sell = (cur['upper_wick_pct'] >= min_wick) or (cur['upper_wick'] >= 1.1 * cur['body'])
            closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
            if swept_high and has_wick_sell and closed_low and cur['rsi'] >= 32.0:
                sig = "SELL"
                sl_buf = max(0.20 * atr, 0.25)
                sl = round(cur['high'] + sl_buf, 2)
                entry = round(cur['high'] - (retest_depth * cur['upper_wick']), 2)
                risk = sl - entry
                if risk > 0:
                    tp = round(entry - (risk * rr), 2)
                else:
                    sig = None

        if not sig:
            i += 1
            continue

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
        be_trig = entry + ((tp - entry) * be_ratio) if sig == "BUY" else entry - ((entry - tp) * be_ratio)
        be_active = False
        outcome = None
        exit_p = entry
        bars_held = 0

        for bar in active:
            bars_held += 1
            if sig == "BUY":
                if bar['low'] <= sl:
                    outcome = "BE" if be_active else "LOSS"
                    exit_p = sl
                    break
                if bar['high'] >= tp:
                    outcome = "WIN"
                    exit_p = tp
                    break
                if not be_active and bar['high'] >= be_trig:
                    be_active = True
                    sl = entry
            elif sig == "SELL":
                if bar['high'] >= sl:
                    outcome = "BE" if be_active else "LOSS"
                    exit_p = sl
                    break
                if bar['low'] <= tp:
                    outcome = "WIN"
                    exit_p = tp
                    break
                if not be_active and bar['low'] <= be_trig:
                    be_active = True
                    sl = entry

        if outcome == "WIN":
            trade_pnl = abs(exit_p - entry) * point_val
        elif outcome == "LOSS":
            trade_pnl = -abs(entry - exit_p) * point_val
        else:
            trade_pnl = 0.0

        trade_records.append({
            "time": entry_time,
            "month": month_key,
            "signal": sig,
            "outcome": outcome,
            "pnl": trade_pnl
        })

        i += max(1, bars_held)

    mt5.shutdown()

    if not trade_records:
        print("No trades found")
        return

    trades_df = pd.DataFrame(trade_records)

    # Monthly Aggregation
    monthly_rows = []
    cum_equity = 0.0
    all_months = sorted(trades_df['month'].unique())

    for m in all_months:
        m_df = trades_df[trades_df['month'] == m]
        m_trades = len(m_df)
        m_wins = len(m_df[m_df['outcome'] == "WIN"])
        m_losses = len(m_df[m_df['outcome'] == "LOSS"])
        m_be = len(m_df[m_df['outcome'] == "BE"])
        decided = m_wins + m_losses
        m_wr = (m_wins / decided * 100.0) if decided > 0 else 0.0
        m_pnl = m_df['pnl'].sum()
        cum_equity += m_pnl
        
        # Profit factor in month
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
    csv_path = os.path.join(current_dir, f"S20_18_{tf_name}_monthly_breakdown.csv")
    m_report_df.to_csv(csv_path, index=False)

    print("\n" + "=" * 95)
    print(f"🏆 S20.18 ({tf_name} Fibo 38.2%) MONTH-BY-MONTH PnL BREAKDOWN (Lot 0.01 | 365 Days)")
    print("=" * 95)
    print(m_report_df.to_string(index=False))
    print("=" * 95)
    
    # Yearly Statistics
    total_trades = m_report_df['Trades'].sum()
    total_wins = m_report_df['Wins'].sum()
    total_losses = m_report_df['Losses'].sum()
    total_be = m_report_df['BE'].sum()
    total_pnl = m_report_df['NetPnL($)'].sum()
    avg_monthly_pnl = m_report_df['NetPnL($)'].mean()
    winning_months = len(m_report_df[m_report_df['NetPnL($)'] > 0])
    total_months = len(m_report_df)
    
    print(f"\n📈 Total Trades: {total_trades} (Wins: {total_wins}, Losses: {total_losses}, BE: {total_be})")
    print(f"💰 Total Net Profit: ${total_pnl:,.2f}")
    print(f"💵 Average PnL per Month: ${avg_monthly_pnl:,.2f} / month")
    print(f"🌟 Winning Months: {winning_months} / {total_months} months ({(winning_months/total_months)*100:.1f}%)")
    print(f"📁 Report saved to: {csv_path}\n")

    return m_report_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monthly Breakdown for S20.18")
    parser.add_argument("--tf", type=str, default="M30", help="Timeframe (M30 or M15)")
    args = parser.parse_args()
    run_monthly_backtest(days=365, tf_name=args.tf)
