# -*- coding: utf-8 -*-
"""backtest_s20_unified.py
Institutional Unified Backtest Runner for all 11 S20 Strategies
(S20.18, S20.19, S20.20, S20.21, S20.22, S20.24, S20.28, S20.301, S20.302, S20.303, S20.304).

Supports:
1. Multi-symbol simulation with Equal Profit Parity Lot Weights (0.01 Gold/Silver, 0.11 GBP, 0.14 EUR, 0.14 JPY).
2. CLI arguments 100% identical to LTS_AUS3 (run_backtest_sim.py).
3. Automatic output of {portfolio}_trades.csv, {portfolio}_daily.csv, and {portfolio}_monthly.csv.
4. Single strategy run (--strategy S20_18) or all 11 combined portfolio run (--strategy all).
"""

import sys
import os
import csv
import bisect
import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

# Path setup
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import config
import s20_institutional_hub as hub
from goal_s20_53_to_100 import init_mt5
from run_master_s20_marathon_201_to_300 import compute_marathon_300_synergies, make_stages

STRATEGY_MAP = {
    "S20_18": 20.18, "20.18": 20.18, "S20.18": 20.18,
    "S20_19": 20.19, "20.19": 20.19, "S20.19": 20.19,
    "S20_20": 20.20, "20.20": 20.20, "S20.20": 20.20,
    "S20_21": 20.21, "20.21": 20.21, "S20.21": 20.21,
    "S20_22": 20.22, "20.22": 20.22, "S20.22": 20.22,
    "S20_24": 20.24, "20.24": 20.24, "S20.24": 20.24,
    "S20_28": 20.28, "20.28": 20.28, "S20.28": 20.28,
    "S20_301": 20.301, "20.301": 20.301, "S20.301": 20.301,
    "S20_302": 20.302, "20.302": 20.302, "S20.302": 20.302,
    "S20_303": 20.303, "20.303": 20.303, "S20.303": 20.303,
    "S20_304": 20.304, "20.304": 20.304, "S20.304": 20.304,
}

ALL_SIDS = [20.18, 20.19, 20.20, 20.21, 20.22, 20.24, 20.28, 20.301, 20.302, 20.303, 20.304]

DEFAULT_SYMBOLS = [
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

def extract_setups_for_strategy(sid, symbol, rates_by_tf, digits, point):
    """Extracts trade setups for a specific strategy and symbol."""
    setups = []
    
    # ── SMC Family (301, 302, 303, 304) ──
    if sid in (20.301, 20.302, 20.303, 20.304):
        from run_s20_304_m5_verified import extract_setups_for_symbol
        dfs = {tf: compute_marathon_300_synergies(r) for tf, r in rates_by_tf.items()}
        raw = extract_setups_for_symbol(symbol, dfs, digits, point)
        for s in raw:
            s["sid"] = sid
            setups.append(s)
        return setups

    # ── Non-SMC Family (20.18 - 20.28) ──
    tf_primary = "M15"
    if sid == 20.19:
        tf_primary = "M5"

    rates = rates_by_tf.get(tf_primary)
    if rates is None or len(rates) < 35:
        return setups

    scale, _ = hub.get_symbol_scale_and_digits(symbol)
    r_eval = rates
    if scale != 1.0:
        r_eval = rates.copy()
        for col in ('open', 'high', 'low', 'close'):
            r_eval[col] = rates[col] * scale

    folder_map = {
        20.18: ("s20.18", "strategy20_18"),
        20.19: ("s20.19", "strategy20_19"),
        20.20: ("s20.20", "strategy20_20"),
        20.21: ("s20.21", "strategy20_21"),
        20.22: ("s20.22", "strategy20_22"),
        20.24: ("s20.24", "strategy20_24"),
        20.28: ("s20.28", "strategy20_28"),
    }
    folder, fname = folder_map[sid]
    mod = hub._get_module(folder, fname)
    if not mod:
        return setups

    try:
        df = mod.compute_indicators_df(r_eval)
        n = len(df)
        for idx in range(30, n):
            res = None
            if sid == 20.18:
                res = mod.evaluate_bar(df, idx, tf=tf_primary, entry_mode="RETEST", rr_ratio=1.8)
            elif sid == 20.19:
                res = mod.evaluate_bar(df, idx, tf=tf_primary, entry_mode="MARKET", target_profit_usd=10.0)
            elif sid == 20.20:
                res = mod.evaluate_asian_mean_reversion(df, idx, tf=tf_primary)
                if res.get("signal") == "WAIT":
                    res = mod.evaluate_asymmetric_rr(df, idx, tf=tf_primary)
            elif sid == 20.21:
                res = mod.evaluate_breaker_block(df, idx, tf=tf_primary)
                if res.get("signal") == "WAIT":
                    res = mod.evaluate_judas_swing(df, idx, tf=tf_primary)
            elif sid == 20.22:
                res = mod.evaluate_vwap_reversion(df, idx, tf=tf_primary)
                if res.get("signal") == "WAIT":
                    res = mod.evaluate_institutional_orb(df, idx, tf=tf_primary)
            elif sid == 20.24:
                res = mod.evaluate_wyckoff_vsa(df, idx, tf=tf_primary)
                if res.get("signal") == "WAIT":
                    res = mod.evaluate_london_close_reversal(df, idx, tf=tf_primary)
            elif sid == 20.28:
                res = mod.evaluate_s20_28_bar(df, idx, tf=tf_primary)

            if res and res.get("signal") in ("BUY", "SELL"):
                entry = res["entry"] / scale if scale != 1.0 else res["entry"]
                sl = res["sl"] / scale if scale != 1.0 else res["sl"]
                tp = res["tp"] / scale if scale != 1.0 else res["tp"]
                risk = abs(entry - sl)
                setups.append({
                    "time": int(df.iloc[idx]['time']),
                    "signal": res["signal"],
                    "entry": round(entry, digits),
                    "sl": round(sl, digits),
                    "tp": round(tp, digits),
                    "risk": risk,
                    "tf": tf_primary,
                    "sid": sid
                })
    except Exception as e:
        print(f"   ⚠️ Error evaluating S{sid} on {symbol}: {e}")

    return sorted(setups, key=lambda x: x['time'])

def simulate_strategy_trades(sid, symbol, m5_bars, m5_times, setups, lot, contract_size, digits, start_ts=None, end_ts=None):
    """Executes setups chronologically on sequential M5 bars."""
    m5_len = len(m5_bars)
    trades_list = []
    busy_until = 0
    is_jpy = "JPY" in symbol.upper()
    is_smc = sid in (20.301, 20.302, 20.303, 20.304)
    stages = make_stages(56 if sid == 20.303 else 55) if is_smc else None
    tp_r = 13.45 if sid == 20.303 else 13.43

    for s in setups:
        s_time = s['time']
        if s_time < busy_until:
            continue
        m5_start = bisect.bisect_right(m5_times, s_time)
        if m5_start >= m5_len:
            continue

        filled = False
        fill_idx = -1
        fill_price = s['entry']

        # Fill window: 12 bars (1 hour)
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
        tp_target = s['tp'] if not is_smc else (round(fill_price + (tp_r * risk), digits) if s['signal'] == 'BUY' else round(fill_price - (tp_r * risk), digits))

        for i in range(fill_idx, m5_len):
            b = m5_bars[i]
            if s['signal'] == 'BUY':
                if b['low'] <= curr_sl:
                    exit_price = curr_sl
                    pnl_pt = (exit_price - fill_price)
                    val = (pnl_pt * rem_volume * lot * contract_size) / (exit_price if is_jpy else 1.0)
                    trade_pnl += val
                    exit_time = b['time']
                    break

                if is_smc:
                    max_fav = b['high'] - fill_price
                    fav_r = max_fav / risk
                    if fav_r >= 0.8 and curr_sl < fill_price:
                        curr_sl = fill_price
                    for r_target, close_pct in stages:
                        if fav_r >= r_target and active_r < r_target:
                            active_r = r_target
                            pnl_pt = (r_target * risk)
                            step_price = fill_price + (r_target * risk)
                            trade_pnl += (pnl_pt * close_pct * lot * contract_size) / (step_price if is_jpy else 1.0)
                            rem_volume -= close_pct
                            new_sl = fill_price + (r_target * 0.70 * risk)
                            if new_sl > curr_sl:
                                curr_sl = new_sl
                    if fav_r >= tp_r:
                        exit_price = tp_target
                        pnl_pt = (exit_price - fill_price)
                        trade_pnl += (pnl_pt * rem_volume * lot * contract_size) / (exit_price if is_jpy else 1.0)
                        exit_time = b['time']
                        break
                else:
                    if b['high'] >= tp_target:
                        exit_price = tp_target
                        pnl_pt = (exit_price - fill_price)
                        trade_pnl += (pnl_pt * rem_volume * lot * contract_size) / (exit_price if is_jpy else 1.0)
                        exit_time = b['time']
                        break
            else:  # SELL
                if b['high'] >= curr_sl:
                    exit_price = curr_sl
                    pnl_pt = (fill_price - exit_price)
                    val = (pnl_pt * rem_volume * lot * contract_size) / (exit_price if is_jpy else 1.0)
                    trade_pnl += val
                    exit_time = b['time']
                    break

                if is_smc:
                    max_fav = fill_price - b['low']
                    fav_r = max_fav / risk
                    if fav_r >= 0.8 and curr_sl > fill_price:
                        curr_sl = fill_price
                    for r_target, close_pct in stages:
                        if fav_r >= r_target and active_r < r_target:
                            active_r = r_target
                            pnl_pt = (r_target * risk)
                            step_price = fill_price - (r_target * risk)
                            trade_pnl += (pnl_pt * close_pct * lot * contract_size) / (step_price if is_jpy else 1.0)
                            rem_volume -= close_pct
                            new_sl = fill_price - (r_target * 0.70 * risk)
                            if new_sl < curr_sl:
                                curr_sl = new_sl
                    if fav_r >= tp_r:
                        exit_price = tp_target
                        pnl_pt = (fill_price - exit_price)
                        trade_pnl += (pnl_pt * rem_volume * lot * contract_size) / (exit_price if is_jpy else 1.0)
                        exit_time = b['time']
                        break
                else:
                    if b['low'] <= tp_target:
                        exit_price = tp_target
                        pnl_pt = (fill_price - exit_price)
                        trade_pnl += (pnl_pt * rem_volume * lot * contract_size) / (exit_price if is_jpy else 1.0)
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
            "leg": f"S{str(sid).replace('.', '_')}_{clean_sym}",
            "symbol": symbol,
            "tf": s.get('tf', 'M5'),
            "type": s['signal'],
            "signal": s['signal'],
            "entry": round(fill_price, digits),
            "sl": round(curr_sl, digits),
            "tp": round(tp_target, digits),
            "lot": round(lot, 2),
            "pnl_usd": round(trade_pnl, 2),
            "outcome": outcome,
            "sid": sid,
        })

    return trades_list

def save_reports(portfolio_name, trades, start_balance, output_dir):
    """Saves {portfolio}_trades.csv, {portfolio}_daily.csv, and {portfolio}_monthly.csv."""
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

def main(default_strategy=None):
    parser = argparse.ArgumentParser(description="Unified S20 Institutional Backtest Engine (11 Strategies)")
    parser.add_argument("--portfolio", default=None, help="Portfolio / Strategy name (e.g. S20_18, S20_304, all)")
    parser.add_argument("--strategy", default=None, help="Strategy alias (e.g. S20_18, S20_304, all)")
    parser.add_argument("--days", type=int, default=365, help="Number of days to backtest (default: 365)")
    parser.add_argument("--start", type=str, default=None, help="Start date (YYYY-MM-DD or DD-MM-YYYY)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD or DD-MM-YYYY)")
    parser.add_argument("--balance", type=float, default=5000.0, help="Starting balance (default: 5000.0)")
    parser.add_argument("--lot", type=float, default=0.01, help="Base lot for gold (default: 0.01)")
    parser.add_argument("--scale", type=float, default=1.0, help="Custom lot scale factor (default: 1.0)")
    parser.add_argument("--spread", type=float, default=0.20, help="Spread in points (default: 0.20)")
    parser.add_argument("--out-dir", default=None, help="Output directory for CSV files (default: reports/{portfolio})")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols to trade (default: all 5 symbols)")
    parser.add_argument("--no-cache", action="store_true", help="Do not load or save cached data")
    args = parser.parse_args()

    # Determine target strategy
    target_name = args.strategy or args.portfolio or default_strategy or "S20_304"
    target_clean = target_name.upper().replace(".", "_")

    if target_clean in ("ALL", "S20_ALL", "PORTFOLIO_ALL"):
        sids_to_run = list(ALL_SIDS)
        portfolio_name = "S20_ALL"
    else:
        sid = STRATEGY_MAP.get(target_name, STRATEGY_MAP.get(target_clean))
        if sid is None:
            print(f"❌ Unknown Strategy '{target_name}'. Available: {list(STRATEGY_MAP.keys())} or 'all'")
            return
        sids_to_run = [sid]
        portfolio_name = f"S{str(sid).replace('.', '_')}"

    out_dir = args.out_dir if args.out_dir else os.path.abspath(os.path.join(root_dir, "reports", portfolio_name.lower()))
    start_balance = args.balance
    base_lot = args.lot
    scale = args.scale

    # Target symbols
    if args.symbols:
        symbols_to_run = [s.strip() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols_to_run = list(DEFAULT_SYMBOLS)

    # Date range
    now_utc = datetime.now(timezone.utc)
    end_dt = parse_date(args.end).replace(tzinfo=timezone.utc) if args.end else now_utc
    start_dt = parse_date(args.start).replace(tzinfo=timezone.utc) if args.start else end_dt - timedelta(days=args.days)
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    fetch_start = start_dt - timedelta(days=60)

    print("=" * 115, flush=True)
    print(f"🏁 RUNNING S20 INSTITUTIONAL BACKTEST: {portfolio_name}", flush=True)
    print(f"   Period: {start_dt.strftime('%d-%m-%Y')} to {end_dt.strftime('%d-%m-%Y')} ({args.days} days)", flush=True)
    print(f"   Starting Balance: ${start_balance:,.2f} | Base Lot: {base_lot} | Scale: {scale}", flush=True)
    print(f"   Strategies ({len(sids_to_run)}): {', '.join([f'S{s}' for s in sids_to_run])}", flush=True)
    print(f"   Active Symbols ({len(symbols_to_run)}): {', '.join(symbols_to_run)}", flush=True)
    print(f"   Output Directory: {out_dir}", flush=True)
    print("=" * 115, flush=True)

    if not init_mt5():
        print("❌ MT5 Initialization Failed")
        return

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
            weight = config.S20_SYMBOL_WEIGHTS.get(sym, 1.0)
            sym_lot = round(base_lot * weight * scale, 2)

            print(f"\n📊 Fetching data for {sym} (Weight: {weight}x -> Lot: {sym_lot}, Digits: {digits})...", flush=True)

            tfs = ['H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15', 'M12', 'M5']
            rates_by_tf = {}
            for tf in tfs:
                tf_const = getattr(mt5, f"TIMEFRAME_{tf}", None)
                if tf_const is not None:
                    r = mt5.copy_rates_range(sym, tf_const, fetch_start, end_dt)
                    if r is not None and len(r) > 0:
                        rates_by_tf[tf] = r

            m5_bars = rates_by_tf.get("M5")
            if m5_bars is None or len(m5_bars) == 0:
                print(f"   ⚠️ No M5 bars found for {sym}, skipping...")
                continue
            m5_times = [int(r['time']) for r in m5_bars]

            sym_trades_total = []
            for s_id in sids_to_run:
                setups = extract_setups_for_strategy(s_id, sym, rates_by_tf, digits, point)
                if setups:
                    t_list = simulate_strategy_trades(
                        sid=s_id,
                        symbol=sym,
                        m5_bars=m5_bars,
                        m5_times=m5_times,
                        setups=setups,
                        lot=sym_lot,
                        contract_size=contract_size,
                        digits=digits,
                        start_ts=start_ts,
                        end_ts=end_ts
                    )
                    sym_trades_total.extend(t_list)

            pnl = sum(t['pnl_usd'] for t in sym_trades_total)
            wins = sum(1 for t in sym_trades_total if t['outcome'] == 'TP')
            losses = sum(1 for t in sym_trades_total if t['outcome'] == 'SL')
            wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0.0

            symbol_summaries[sym] = {
                "trades": len(sym_trades_total),
                "wins": wins,
                "losses": losses,
                "wr": wr,
                "pnl": pnl,
                "lot": sym_lot
            }
            print(f"   {sym} -> {len(sym_trades_total)} trades | WinRate: {wr:.1f}% | Net P&L: ${pnl:,.2f}", flush=True)
            all_trades.extend(sym_trades_total)

    finally:
        mt5.shutdown()
        print("\nMT5 Shutdown completed.")

    all_trades.sort(key=lambda x: x['fill_time_ts'])

    print(f"\nProcessing reports for {portfolio_name} (found {len(all_trades)} trades)...")
    save_reports(portfolio_name, all_trades, start_balance, out_dir)

    total_trades = len(all_trades)
    wins = sum(1 for t in all_trades if t['outcome'] == 'TP')
    losses = sum(1 for t in all_trades if t['outcome'] == 'SL')
    bes = sum(1 for t in all_trades if t['outcome'] == 'BE')
    total_pnl = sum(t['pnl_usd'] for t in all_trades)
    wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0.0

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
    print(f" 🏆 {portfolio_name} VERIFIED MULTI-ASSET PERFORMANCE SUMMARY")
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
