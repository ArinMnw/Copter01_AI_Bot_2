# -*- coding: utf-8 -*-
"""run_s20_304_m5_verified.py
Official 100% Verifiable Multi-Asset Backtest Runner for Strategy S20.304
Supports all 5 symbols (XAUUSD.iux, XAGUSD.iux, EURUSD.iux, GBPUSD.iux, USDJPY.iux)
with symbol lot weights, CLI arguments identical to LTS_AUS3 (run_backtest_sim.py),
and automatic CSV reporting (trades, daily, monthly).
"""
import sys
import os
import csv
import bisect
import pickle
import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

# Add repo root and strategy dir to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
strategy_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if strategy_dir not in sys.path:
    sys.path.insert(0, strategy_dir)

import config
from goal_s20_53_to_100 import init_mt5
from run_master_s20_marathon_201_to_300 import compute_marathon_300_synergies, make_stages

# Symbol lot weights for Equal Profit Parity (Target ~$38,400/yr profit matching 0.01 Gold)
DEFAULT_SYMBOL_WEIGHTS = {
    "XAUUSD.iux": 1.0,   # 0.01 lot
    "XAGUSD.iux": 1.0,   # 0.01 lot
    "GBPUSD.iux": 11.0,  # 0.11 lot
    "EURUSD.iux": 14.0,  # 0.14 lot
    "USDJPY.iux": 14.0,  # 0.14 lot
}

ALL_SYMBOLS = [
    "XAUUSD.iux",
    "XAGUSD.iux",
    "EURUSD.iux",
    "GBPUSD.iux",
    "USDJPY.iux",
]

def format_ts_to_bkk(ts):
    if not ts or ts == "-":
        return "-"
    bkk_tz = timezone(timedelta(hours=7))
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(bkk_tz).strftime('%d-%m-%Y %H:%M:%S')

def parse_date(date_str):
    if not date_str:
        return None
    date_str = date_str.strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date string: {date_str}")

def extract_setups_for_symbol(symbol, dfs, digits, point):
    """Extract institutional setups adapted for commodity and forex pairs."""
    setups = []
    sym_upper = symbol.upper()

    if "XAU" in sym_upper:
        min_atr = 0.05
        min_sl_buf = 0.22
    elif "XAG" in sym_upper:
        min_atr = 0.001
        min_sl_buf = 0.015
    elif "JPY" in sym_upper:
        min_atr = 2.0 * point
        min_sl_buf = 2.0 * point
    else:  # EURUSD, GBPUSD, etc.
        min_atr = 2.0 * point
        min_sl_buf = 2.0 * point

    for tf, df_tf in dfs.items():
        if df_tf is None or len(df_tf) == 0:
            continue
        for cur in df_tf.to_dict('records'):
            if pd.isna(cur['atr']) or cur['atr'] <= min_atr or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
                continue

            swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or \
                        (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or \
                        (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or \
                        (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or \
                        (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl']) or \
                        cur['swept_htf_low'] or cur['is_spring']

            swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or \
                         (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or \
                         (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or \
                         (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or \
                         (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh']) or \
                         cur['swept_htf_high'] or cur['is_utad']

            bull_ob = cur['bull_ob_zone']
            bear_ob = cur['bear_ob_zone']
            ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
            ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)
            bpr_tap_bull = (cur['has_bpr'] and cur['low'] <= cur['bpr_high'] and cur['high'] >= cur['bpr_low'])
            bpr_tap_bear = (cur['has_bpr'] and cur['high'] >= cur['bpr_low'] and cur['low'] <= cur['bpr_high'])
            is_abs_buy = cur['is_absorption_buy']
            is_abs_sell = cur['is_absorption_sell']
            ifvg_buy = cur['ifvg_tap_buy']
            ifvg_sell = cur['ifvg_tap_sell']
            bb_buy = (not pd.isna(cur.get('breaker_bull_zone')) and cur['low'] <= cur['breaker_bull_zone'])
            bb_sell = (not pd.isna(cur.get('breaker_bear_zone')) and cur['high'] >= cur['breaker_bear_zone'])
            is_overlap = cur['is_ldn_ny_overlap']

            has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
            has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
            closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
            closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
            is_comp = cur['compression_ratio'] <= 0.70

            sig = "BUY" if ((swept_low or ob_mitigated_bull or bpr_tap_bull or is_abs_buy or ifvg_buy or bb_buy) and has_wick_buy and closed_high) else \
                  ("SELL" if ((swept_high or ob_mitigated_bear or bpr_tap_bear or is_abs_sell or ifvg_sell or bb_sell) and has_wick_sell and closed_low) else None)

            if sig:
                is_hc = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) or \
                        (bpr_tap_bull if sig == "BUY" else bpr_tap_bear) or \
                        (is_abs_buy if sig == "BUY" else is_abs_sell) or \
                        (ifvg_buy if sig == "BUY" else ifvg_sell) or \
                        (bb_buy if sig == "BUY" else bb_sell)

                sl_mult = (0.188 - 0.002 if is_overlap else 0.188) if is_hc else (0.190 if is_comp else 0.195)
                sl_buf = max(sl_mult * cur['atr'], min_sl_buf)
                active_depth = 0.121 if is_hc else (0.124 if is_comp else 0.125)

                entry = round(cur['low'] + (active_depth * cur['lower_wick']), digits) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), digits)
                sl = round(cur['low'] - sl_buf, digits) if sig == "BUY" else round(cur['high'] + sl_buf, digits)
                risk = entry - sl if sig == "BUY" else sl - entry

                if risk > 0:
                    setups.append({
                        "time": int(cur['time']),
                        "signal": sig,
                        "entry": entry,
                        "sl": sl,
                        "risk": risk,
                        "atr": cur['atr'],
                        "tf": tf
                    })

    return sorted(setups, key=lambda x: x['time'])

def run_asset_sim(symbol, m5_bars, m5_times, setups, tp_r=13.43, stages=None,
                   lot=0.01, contract_size=100.0, digits=2, start_ts=None, end_ts=None):
    """Simulates S20.304 execution on sequential M5 bars with dynamic lot and contract point value."""
    if stages is None:
        stages = make_stages(55)
    m5_len = len(m5_bars)
    be_trigger = 0.8
    busy_until = 0
    trades_list = []
    is_jpy = "JPY" in symbol.upper()

    for s in setups:
        s_time = s['time']
        if s_time < busy_until:
            continue
        m5_start = bisect.bisect_right(m5_times, s_time)
        if m5_start >= m5_len:
            continue

        filled = False
        fill_idx = -1
        fill_price = 0.0
        for i in range(m5_start, min(m5_start + 12, m5_len)):
            b = m5_bars[i]
            if s['signal'] == 'BUY' and b['low'] <= s['entry']:
                filled = True
                fill_idx = i
                fill_price = s['entry']
                break
            elif s['signal'] == 'SELL' and b['high'] >= s['entry']:
                filled = True
                fill_idx = i
                fill_price = s['entry']
                break
        if not filled:
            continue

        fill_time = int(m5_bars[fill_idx]['time'])
        # Date range filter for trade entry
        if start_ts and fill_time < start_ts:
            continue
        if end_ts and fill_time > end_ts:
            continue

        risk = s['risk']
        curr_sl = s['sl']
        active_r = 0.0
        exit_price = None
        exit_time = 0
        rem_volume = 1.0
        trade_pnl = 0.0
        tp_target = round(fill_price + (tp_r * risk), digits) if s['signal'] == 'BUY' else round(fill_price - (tp_r * risk), digits)

        for i in range(fill_idx, m5_len):
            b = m5_bars[i]
            if s['signal'] == 'BUY':
                if b['low'] <= curr_sl:
                    exit_price = curr_sl
                    pnl_pt = (exit_price - fill_price)
                    if is_jpy:
                        trade_pnl += (pnl_pt * rem_volume * lot * contract_size) / exit_price
                    else:
                        trade_pnl += pnl_pt * rem_volume * lot * contract_size
                    exit_time = b['time']
                    break
                max_fav = b['high'] - fill_price
                fav_r = max_fav / risk
                if fav_r >= be_trigger and curr_sl < fill_price:
                    curr_sl = fill_price
                for r_target, close_pct in stages:
                    if fav_r >= r_target and active_r < r_target:
                        active_r = r_target
                        pnl_pt = (r_target * risk)
                        step_price = fill_price + (r_target * risk)
                        if is_jpy:
                            trade_pnl += (pnl_pt * close_pct * lot * contract_size) / step_price
                        else:
                            trade_pnl += pnl_pt * close_pct * lot * contract_size
                        rem_volume -= close_pct
                        new_sl = fill_price + (r_target * 0.70 * risk)
                        if new_sl > curr_sl:
                            curr_sl = new_sl
                if fav_r >= tp_r:
                    exit_price = tp_target
                    pnl_pt = (exit_price - fill_price)
                    if is_jpy:
                        trade_pnl += (pnl_pt * rem_volume * lot * contract_size) / exit_price
                    else:
                        trade_pnl += pnl_pt * rem_volume * lot * contract_size
                    exit_time = b['time']
                    break
            else:  # SELL
                if b['high'] >= curr_sl:
                    exit_price = curr_sl
                    pnl_pt = (fill_price - exit_price)
                    if is_jpy:
                        trade_pnl += (pnl_pt * rem_volume * lot * contract_size) / exit_price
                    else:
                        trade_pnl += pnl_pt * rem_volume * lot * contract_size
                    exit_time = b['time']
                    break
                max_fav = fill_price - b['low']
                fav_r = max_fav / risk
                if fav_r >= be_trigger and curr_sl > fill_price:
                    curr_sl = fill_price
                for r_target, close_pct in stages:
                    if fav_r >= r_target and active_r < r_target:
                        active_r = r_target
                        pnl_pt = (r_target * risk)
                        step_price = fill_price - (r_target * risk)
                        if is_jpy:
                            trade_pnl += (pnl_pt * close_pct * lot * contract_size) / step_price
                        else:
                            trade_pnl += pnl_pt * close_pct * lot * contract_size
                        rem_volume -= close_pct
                        new_sl = fill_price - (r_target * 0.70 * risk)
                        if new_sl < curr_sl:
                            curr_sl = new_sl
                if fav_r >= tp_r:
                    exit_price = tp_target
                    pnl_pt = (fill_price - exit_price)
                    if is_jpy:
                        trade_pnl += (pnl_pt * rem_volume * lot * contract_size) / exit_price
                    else:
                        trade_pnl += pnl_pt * rem_volume * lot * contract_size
                    exit_time = b['time']
                    break

        if exit_price is None:
            continue

        busy_until = exit_time
        outcome = "TP" if trade_pnl > 0.01 else ("SL" if trade_pnl < -0.01 else "BE")

        clean_sym = symbol.split('.')[0]
        trades_list.append({
            "fill_time_ts": fill_time,
            "exit_time_ts": int(exit_time),
            "leg": f"S20_304_{clean_sym}",
            "symbol": symbol,
            "tf": s['tf'],
            "signal": s['signal'],
            "entry": round(fill_price, digits),
            "sl": round(s['sl'], digits),
            "tp": round(tp_target, digits),
            "lot": round(lot, 2),
            "pnl_usd": round(trade_pnl, 2),
            "outcome": outcome,
        })

    return trades_list

def save_reports(portfolio_name, trades, start_balance, output_dir):
    """Calculates running balance and outputs trades, daily, and monthly CSV files matching LTS_AUS3."""
    os.makedirs(output_dir, exist_ok=True)
    trades.sort(key=lambda x: x.get("fill_time_ts", 0))

    # 1. Trades CSV
    running_balance = start_balance
    trades_rows = []
    for t in trades:
        pnl = t.get("pnl_usd", 0.0)
        running_balance += pnl
        trades_rows.append({
            "Time (BKK)": format_ts_to_bkk(t.get("fill_time_ts")),
            "Close Time": format_ts_to_bkk(t.get("exit_time_ts")),
            "Leg": t.get("leg", portfolio_name),
            "TF": t.get("tf", "M5"),
            "Type": t.get("signal", ""),
            "Entry": t.get("entry", 0.0),
            "SL": t.get("sl", 0.0),
            "TP": t.get("tp", 0.0),
            "Lot": round(t.get("lot", 0.01), 2),
            "P&L": round(pnl, 2),
            "Balance": round(running_balance, 2),
            "Outcome": t.get("outcome", "")
        })

    trades_path = os.path.join(output_dir, f"{portfolio_name}_trades.csv")
    if trades_rows:
        df_trades = pd.DataFrame(trades_rows)
        df_trades.to_csv(trades_path, index=False, encoding="utf-8")
        print(f"Saved: {trades_path} ({len(trades_rows)} trades)")
    else:
        with open(trades_path, "w", newline="", encoding="utf-8") as f:
            f.write("Time (BKK),Close Time,Leg,TF,Type,Entry,SL,TP,Lot,P&L,Balance,Outcome\n")
        print(f"Saved empty placeholder: {trades_path}")

    # 2. Daily CSV
    daily_records = []
    if trades_rows:
        df = pd.DataFrame(trades_rows)
        df['date'] = df['Time (BKK)'].apply(lambda x: x.split(" ")[0] if x != "-" else "-")
        df = df[df['date'] != "-"]

        running_daily_balance = start_balance
        for d, grp in df.groupby('date', sort=False):
            tp = (grp['Outcome'] == 'TP').sum()
            sl = (grp['Outcome'] == 'SL').sum()
            net = grp['P&L'].sum()
            running_daily_balance += net
            wr = tp / (tp + sl) * 100 if tp + sl > 0 else 0.0
            daily_records.append({
                "Date": d,
                "Trades": len(grp),
                "Win": tp,
                "Loss": sl,
                "Net Profit": round(net, 2),
                "Win Rate (%)": round(wr, 2),
                "Balance": round(running_daily_balance, 2)
            })

    daily_path = os.path.join(output_dir, f"{portfolio_name}_daily.csv")
    if daily_records:
        pd.DataFrame(daily_records).to_csv(daily_path, index=False, encoding="utf-8")
        print(f"Saved: {daily_path}")
    else:
        with open(daily_path, "w", newline="", encoding="utf-8") as f:
            f.write("Date,Trades,Win,Loss,Net Profit,Win Rate (%),Balance\n")
        print(f"Saved empty placeholder: {daily_path}")

    # 3. Monthly CSV
    monthly_records = []
    if trades_rows and daily_records:
        df = pd.DataFrame(trades_rows)
        df['month'] = df['Time (BKK)'].apply(lambda x: "-".join(x.split(" ")[0].split("-")[1:][::-1]) if x != "-" else "-")
        df = df[df['month'] != "-"]

        running_monthly_balance = start_balance
        for m, grp in df.groupby('month', sort=False):
            tp = (grp['Outcome'] == 'TP').sum()
            sl = (grp['Outcome'] == 'SL').sum()
            net = grp['P&L'].sum()
            running_monthly_balance += net
            wr = tp / (tp + sl) * 100 if tp + sl > 0 else 0.0
            monthly_records.append({
                "Month": m,
                "Trades": len(grp),
                "Win": tp,
                "Loss": sl,
                "Net Profit": round(net, 2),
                "Win Rate (%)": round(wr, 2),
                "Balance": round(running_monthly_balance, 2)
            })

    monthly_path = os.path.join(output_dir, f"{portfolio_name}_monthly.csv")
    if monthly_records:
        pd.DataFrame(monthly_records).to_csv(monthly_path, index=False, encoding="utf-8")
        print(f"Saved: {monthly_path}")
    else:
        with open(monthly_path, "w", newline="", encoding="utf-8") as f:
            f.write("Month,Trades,Win,Loss,Net Profit,Win Rate (%),Balance\n")
        print(f"Saved empty placeholder: {monthly_path}")

def main():
    parser = argparse.ArgumentParser(description="Institutional S20.304 Verified Multi-Asset Backtest Simulation")
    parser.add_argument("--portfolio", default="S20_304", help="Portfolio name (default: S20_304)")
    parser.add_argument("--days", type=int, default=365, help="Number of days to backtest (default: 365)")
    parser.add_argument("--start", type=str, default=None, help="Start date (YYYY-MM-DD or DD-MM-YYYY)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD or DD-MM-YYYY)")
    parser.add_argument("--balance", type=float, default=5000.0, help="Starting balance (default: 5000.0)")
    parser.add_argument("--lot", type=float, default=0.01, help="Base lot for gold (default: 0.01)")
    parser.add_argument("--scale", type=float, default=1.0, help="Custom lot scale factor (default: 1.0)")
    parser.add_argument("--spread", type=float, default=0.20, help="Spread in points (default: 0.20)")
    parser.add_argument("--out-dir", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "reports", "s20_304")),
                        help="Output directory for CSV files (default: reports/s20_304)")
    parser.add_argument("--symbols", type=str, default=None,
                        help="Comma-separated symbols to trade (default: all 5 symbols)")
    parser.add_argument("--no-cache", action="store_true", help="Do not load or save cached data")
    args = parser.parse_args()

    portfolio_name = args.portfolio
    start_balance = args.balance
    base_lot = args.lot
    scale = args.scale

    # Resolve target symbols
    if args.symbols:
        symbols_to_run = [s.strip() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols_to_run = list(ALL_SYMBOLS)

    # Resolve date range
    now_utc = datetime.now(timezone.utc)
    if args.end:
        end_dt = parse_date(args.end).replace(tzinfo=timezone.utc)
    else:
        end_dt = now_utc

    if args.start:
        start_dt = parse_date(args.start).replace(tzinfo=timezone.utc)
    else:
        start_dt = end_dt - timedelta(days=args.days)

    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    # Lookback buffer for indicator calculations
    fetch_start = start_dt - timedelta(days=60)

    print("=" * 115, flush=True)
    print(f"🏁 RUNNING S20.304 MULTI-ASSET BACKTEST: {portfolio_name}", flush=True)
    print(f"   Period: {start_dt.strftime('%d-%m-%Y')} to {end_dt.strftime('%d-%m-%Y')} ({args.days} days)", flush=True)
    print(f"   Starting Balance: ${start_balance:,.2f} | Base Lot: {base_lot} | Scale: {scale}", flush=True)
    print(f"   Active Symbols ({len(symbols_to_run)}): {', '.join(symbols_to_run)}", flush=True)
    print(f"   Output Directory: {args.out_dir}", flush=True)
    print("=" * 115, flush=True)

    if not init_mt5():
        print("❌ MT5 Initialization Failed")
        return

    stages_55 = make_stages(55)
    all_trades = []
    symbol_summaries = {}

    try:
        for sym in symbols_to_run:
            mt5.symbol_select(sym, True)
            sinfo = mt5.symbol_info(sym)
            if not sinfo:
                print(f"⚠️ Symbol {sym} not found in MT5, skipping...")
                continue

            digits = sinfo.digits
            point = sinfo.point
            contract_size = sinfo.trade_contract_size

            # Determine lot for symbol based on weight
            weight = DEFAULT_SYMBOL_WEIGHTS.get(sym, 1.0)
            sym_lot = round(base_lot * weight * scale, 2)

            print(f"\n📊 Processing {sym} (Weight: {weight}x -> Lot: {sym_lot}, Digits: {digits}, Contract: {contract_size:,.0f})...", flush=True)

            tfs = ['H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15', 'M12']
            rates = {}
            for tf in tfs:
                tf_const = getattr(mt5, f"TIMEFRAME_{tf}", None)
                if tf_const is not None:
                    r = mt5.copy_rates_range(sym, tf_const, fetch_start, end_dt)
                    if r is not None and len(r) > 0:
                        rates[tf] = r

            # Fetch M5 execution bars
            m5_bars = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, fetch_start, end_dt)
            if m5_bars is None or len(m5_bars) == 0:
                print(f"   ⚠️ No M5 bars found for {sym}, skipping...")
                continue
            m5_times = [int(r['time']) for r in m5_bars]

            # Compute synergies
            dfs = {tf: compute_marathon_300_synergies(r) for tf, r in rates.items()}

            # Extract setups
            setups = extract_setups_for_symbol(sym, dfs, digits, point)
            print(f"   Extracted {len(setups)} raw setups across all timeframes", flush=True)

            # Simulate
            sym_trades = run_asset_sim(
                symbol=sym,
                m5_bars=m5_bars,
                m5_times=m5_times,
                setups=setups,
                tp_r=13.43,
                stages=stages_55,
                lot=sym_lot,
                contract_size=contract_size,
                digits=digits,
                start_ts=start_ts,
                end_ts=end_ts
            )

            pnl = sum(t['pnl_usd'] for t in sym_trades)
            wins = sum(1 for t in sym_trades if t['outcome'] == 'TP')
            losses = sum(1 for t in sym_trades if t['outcome'] == 'SL')
            wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0.0

            symbol_summaries[sym] = {
                "trades": len(sym_trades),
                "wins": wins,
                "losses": losses,
                "wr": wr,
                "pnl": pnl,
                "lot": sym_lot
            }
            print(f"   {sym} -> {len(sym_trades)} trades | WinRate: {wr:.1f}% | Net P&L: ${pnl:,.2f}", flush=True)

            all_trades.extend(sym_trades)

    finally:
        mt5.shutdown()
        print("\nMT5 Shutdown completed.")

    # Sort all trades chronologically across all symbols
    all_trades.sort(key=lambda x: x['fill_time_ts'])

    # Save reports (Trades, Daily, Monthly CSV)
    print(f"\nProcessing reports for {portfolio_name} (found {len(all_trades)} trades)...")
    save_reports(portfolio_name, all_trades, start_balance, args.out_dir)

    # Compute overall performance metrics
    total_trades = len(all_trades)
    wins = sum(1 for t in all_trades if t['outcome'] == 'TP')
    losses = sum(1 for t in all_trades if t['outcome'] == 'SL')
    bes = sum(1 for t in all_trades if t['outcome'] == 'BE')
    total_pnl = sum(t['pnl_usd'] for t in all_trades)
    wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0.0

    # Drawdown calculation
    running = start_balance
    peak = start_balance
    max_dd = 0.0
    for t in all_trades:
        running += t['pnl_usd']
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd

    final_balance = start_balance + total_pnl

    print("\n" + "=" * 115)
    print(f" 🏆 S20.304 MULTI-ASSET VERIFIED PERFORMANCE SUMMARY ({portfolio_name})")
    print("=" * 115)
    print(f" Initial Balance:          ${start_balance:,.2f}")
    print(f" Final Balance:            ${final_balance:,.2f}")
    print(f" Net Profit:               ${total_pnl:,.2f} ({(total_pnl / start_balance * 100):+.1f}%)")
    print(f" Max Drawdown:             ${max_dd:,.2f} ({(max_dd / start_balance * 100):.1f}%)")
    print(f" Total Trades Executed:    {total_trades:,} (W: {wins} | L: {losses} | BE: {bes})")
    print(f" Overall Win Rate:         {wr:.1f}%")
    print("-" * 115)
    print(f" {'Symbol':<15} {'Lot':<8} {'Trades':<10} {'Wins':<8} {'Losses':<8} {'Win Rate':<12} {'Net P&L ($)':<15}")
    print("-" * 115)
    for sym, st in symbol_summaries.items():
        print(f" {sym:<15} {st['lot']:<8.2f} {st['trades']:<10} {st['wins']:<8} {st['losses']:<8} {st['wr']:<12.1f}% ${st['pnl']:<14,.2f}")
    print("=" * 115)

if __name__ == "__main__":
    main()
