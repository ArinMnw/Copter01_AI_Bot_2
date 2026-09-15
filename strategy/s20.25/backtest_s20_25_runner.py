# -*- coding: utf-8 -*-
"""backtest_s20_25_runner.py — 365-Day Backtest & Monthly Tear Sheet for S20.25 Fusion:
Compares:
1. S20.25 Standalone (Sweep + Absorption only)
2. S20.25 Full Fusion (Sweep + Absorption + VWAP Statistical Confluence)
Measures whether combining strategies makes the system strictly more accurate!
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

import strategy20_25


def init_mt5():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()


def simulate_fusion(rates, df, require_vwap=True, total_lot=0.02, tf_name="M30"):
    contract_size = 100.0
    scalp_lot = total_lot / 2.0
    runner_lot = total_lot / 2.0
    point_val_scalp = contract_size * scalp_lot
    point_val_runner = contract_size * runner_lot

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
        res = strategy20_25.evaluate_confluence_bar(df, i, tf=tf_name, require_vwap=require_vwap)
        if not res:
            i += 1
            continue

        sig = res["signal"]
        entry = res["entry"]
        sl = res["sl"]
        tp1 = res["tp_scalp"]
        tp2 = res["tp_runner"]
        be_trig = entry + ((tp1 - entry) * 0.40) if sig == "BUY" else entry - ((entry - tp1) * 0.40)

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
            "month": month_key,
            "outcome": outcome,
            "pnl": trade_pnl
        })

        i += max(1, bars_held)

    total_wins = full_wins + scalp_wins
    decided = total_wins + full_losses
    wr = (total_wins / decided * 100.0) if decided > 0 else 0.0

    trades_df = pd.DataFrame(trade_records) if trade_records else pd.DataFrame()
    m_summary = {}
    if not trades_df.empty:
        for m, grp in trades_df.groupby('month'):
            m_summary[m] = round(grp['pnl'].sum(), 2)

    gross_w = trades_df[trades_df['pnl'] > 0]['pnl'].sum() if not trades_df.empty else 0.0
    gross_l = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum()) if not trades_df.empty else 0.0
    pf = (gross_w / gross_l) if gross_l > 0 else 99.0

    return {
        "trades": trades, "wins": total_wins, "full_wins": full_wins, "scalp_wins": scalp_wins,
        "losses": full_losses, "be": breakevens, "wr": wr, "pnl": pnl, "pf": pf, "max_dd": max_dd,
        "monthly": m_summary
    }


def main():
    if not init_mt5():
        print("❌ MT5 initialize failed")
        return

    symbol = "XAUUSD.iux"
    days = 365
    total_lot = 0.02
    tf_name = "M30"

    print("=========================================================================")
    print(f"  🔬 S20.25 MULTI-STRATEGY CONFLUENCE FUSION (365-Day Synergy Test)")
    print(f"  Symbol: {symbol} | TF: {tf_name} | Total Lot: {total_lot} (0.01 Scalp + 0.01 Runner)")
    print("=========================================================================\n")

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    tf_code = mt5.TIMEFRAME_M30
    rates = mt5.copy_rates_range(symbol, tf_code, start_time, end_time)
    if rates is None or len(rates) < 100:
        print("❌ Insufficient rates data")
        mt5.shutdown()
        return

    print(f"Loaded {len(rates):,} bars")
    df = strategy20_25.compute_indicators_df(rates)

    # 1. Standalone (No VWAP confluence)
    print("Testing Standalone Mode (Sweep + Absorption only) ... ", end="", flush=True)
    res_single = simulate_fusion(rates, df, require_vwap=False, total_lot=total_lot, tf_name=tf_name)
    print(f"Trades: {res_single['trades']} | WR: {res_single['wr']:.1f}% | Net: ${res_single['pnl']:+.2f} | PF: {res_single['pf']:.2f} | DD: ${res_single['max_dd']:.2f}")

    # 2. Full Fusion (Sweep + Absorption + VWAP Statistical Confluence)
    print("Testing Full Fusion Mode (Sweep + Absorption + VWAP) ... ", end="", flush=True)
    res_fusion = simulate_fusion(rates, df, require_vwap=True, total_lot=total_lot, tf_name=tf_name)
    print(f"Trades: {res_fusion['trades']} | WR: {res_fusion['wr']:.1f}% | Net: ${res_fusion['pnl']:+.2f} | PF: {res_fusion['pf']:.2f} | DD: ${res_fusion['max_dd']:.2f}")

    mt5.shutdown()

    # Comparison Table
    comp_data = [
        {
            "Mode": "1. Standalone (Sweep Only)",
            "Trades": res_single["trades"],
            "Wins": res_single["wins"],
            "Losses": res_single["losses"],
            "BE": res_single["be"],
            "WinRate%": round(res_single["wr"], 1),
            "NetProfit($)": round(res_single["pnl"], 2),
            "ProfitFactor": round(res_single["pf"], 2),
            "MaxDD($)": round(res_single["max_dd"], 2)
        },
        {
            "Mode": "2. Full Fusion (+VWAP Synergy) 👑",
            "Trades": res_fusion["trades"],
            "Wins": res_fusion["wins"],
            "Losses": res_fusion["losses"],
            "BE": res_fusion["be"],
            "WinRate%": round(res_fusion["wr"], 1),
            "NetProfit($)": round(res_fusion["pnl"], 2),
            "ProfitFactor": round(res_fusion["pf"], 2),
            "MaxDD($)": round(res_fusion["max_dd"], 2)
        }
    ]

    print("\n" + "=" * 95)
    print("🏆 S20.25 CONFLUENCE SYNERGY COMPARISON: DOES COMBINING MAKE IT MORE ACCURATE?")
    print("=" * 95)
    print(pd.DataFrame(comp_data).to_string(index=False))
    print("=" * 95)

    # Monthly comparison
    all_months = sorted(list(set(list(res_single["monthly"].keys()) + list(res_fusion["monthly"].keys()))))
    m_rows = []
    for m in all_months:
        m_rows.append({
            "Month": m,
            "Standalone_PnL($)": res_single["monthly"].get(m, 0.0),
            "Fusion_VWAP_PnL($)": res_fusion["monthly"].get(m, 0.0)
        })
    m_df = pd.DataFrame(m_rows)
    csv_path = os.path.join(current_dir, "S20_25_fusion_comparison.csv")
    m_df.to_csv(csv_path, index=False)

    print("\n📅 S20.25 MONTH-BY-MONTH PnL COMPARISON:")
    print("=" * 70)
    print(m_df.to_string(index=False))
    print("=" * 70)
    print(f"📁 Detailed CSV saved to: {csv_path}\n")


if __name__ == "__main__":
    main()
