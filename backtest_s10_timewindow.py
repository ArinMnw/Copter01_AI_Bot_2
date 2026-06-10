import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import argparse
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import config
import json
import os

# Parse arguments
parser = argparse.ArgumentParser(description='Backtest S10 signals for a specific Bangkok datetime window')
parser.add_argument('--start', type=str, required=True,
                    help='Window start (YYYY-MM-DDTHH:MM or YYYY-MM-DD HH:MM) in Bangkok timezone')
parser.add_argument('--end', type=str, required=True,
                    help='Window end (YYYY-MM-DDTHH:MM or YYYY-MM-DD HH:MM) in Bangkok timezone')
parser.add_argument('--tf', type=str, required=False,
                    help='Timeframe name to backtest (e.g., M5). If omitted, all timeframes are tested')
parser.add_argument('--since', type=str, required=False,
                    help='Simulation start date/time (YYYY-MM-DDTHH:MM or YYYY-MM-DD HH:MM) in Bangkok timezone')
parser.add_argument('--exclude-cancelled', '--only-filled', action='store_true', dest='exclude_cancelled',
                    help='Exclude trades/orders that were cancelled before fill (e.g., CANCEL, PD_FAIL, OPEN_PENDING)')
parser.add_argument('--symbol', type=str, required=False,
                    help='Symbol to backtest (e.g., XAUUSD.iux). If omitted, loads from bot_state.json')
args = parser.parse_args()

# Now import from sim_s10_backtest (which will use updated config values)
import sim_s10_backtest
from sim_s10_backtest import (
    backtest_tf,
    TF_MAP,
    s10_runtime_feature_coverage,
    s10_unreplayed_active_features,
    sync_strategy10_runtime_config,
    to_bkk,
)

SYMBOL = config.SYMBOL
VOLUME = 0.01

# Helper to parse datetime
def parse_bkk_dt(dt_str: str) -> datetime:
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    raise ValueError(f'Invalid datetime format: {dt_str}. Use YYYY-MM-DD HH:MM:SS, YYYY-MM-DDTHH:MM:SS, YYYY-MM-DD HH:MM or YYYY-MM-DDTHH:MM')

window_start_bkk = parse_bkk_dt(args.start)
window_end_bkk   = parse_bkk_dt(args.end)

if window_end_bkk < window_start_bkk:
    raise ValueError('End datetime must be after start datetime')

window_start_utc = window_start_bkk.replace(tzinfo=timezone.utc)
window_end_utc   = window_end_bkk.replace(tzinfo=timezone.utc)

if args.since:
    since_bkk = parse_bkk_dt(args.since)
    since_utc = since_bkk.replace(tzinfo=timezone.utc)
    # We need to subtract 7 hours to get UTC from BKK timezone
    # Wait, the parser parses it as local time, but we treat it as UTC for sim_s10_backtest.SINCE
    # Let's adjust since_utc to match BKK -> UTC offset
    since_utc = since_utc - timedelta(hours=7)
    sim_s10_backtest.SINCE = since_utc

def run_backtest():
    if not mt5.initialize():
        print('MT5 init failed:', mt5.last_error())
        return

    # Load auto trade config state from bot_state.json
    restore_info = config.restore_runtime_state()
    state_symbol = ""
    try:
        if os.path.exists(config.STATE_FILE):
            with open(config.STATE_FILE, "r", encoding="utf-8") as f:
                state_symbol = str((json.load(f) or {}).get("symbol", "") or "")
    except Exception:
        state_symbol = ""
    selected_symbol = args.symbol or state_symbol or config.SYMBOL
    if selected_symbol:
        config.set_runtime_symbol(selected_symbol)
        sim_s10_backtest.SYMBOL = selected_symbol
        global SYMBOL
        SYMBOL = selected_symbol
    sync_strategy10_runtime_config()

    print(f'Symbol : {SYMBOL}')
    print(f'Restore: {restore_info}')
    print(f'Window : {window_start_bkk} → {window_end_bkk} (Bangkok timezone)')
    print(f'S10 Settings: active_strategies[10]={config.active_strategies.get(10, False)}')
    print(f'              CRT_BAR_MODE={getattr(config, "CRT_BAR_MODE", "2bar")} | CRT_WAIT_HTF_CLOSE={getattr(config, "CRT_WAIT_HTF_CLOSE", False)} | CRT_PARENT_MIN_BODY_PCT={getattr(config, "CRT_PARENT_MIN_BODY_PCT", 0.50)}')
    print(f'              PDFIBOPLUS_ENABLED={getattr(config, "PDFIBOPLUS_ENABLED", True)} | PD_SKIP_SIDS=9,10,13,14,15,16')
    print('S10 Coverage:')
    for item in s10_runtime_feature_coverage():
        if item["runtime"] == "skip_s10":
            status = "runtime skip"
        elif item["replay"] == "apply":
            status = "replayed"
        elif item["config_on"]:
            status = "ACTIVE GAP"
        else:
            status = "off gap"
        print(f'  {item["name"]:<34} config={str(item["config_on"]):<5} {status:<12} {item["note"]}')
    gaps = s10_unreplayed_active_features()
    if gaps:
        print('WARNING: Active S10 runtime features not replayed yet:')
        for item in gaps:
            print(f'  - {item["name"]}: {item["note"]}')
    print('=' * 65)

    if not config.active_strategies.get(10, False):
        print("❌ S10 is disabled (OFF) in config! Skip backtest.")
        mt5.shutdown()
        return

    grand_total = 0.0
    all_trades = []

    HTF_TO_LTF = {
        "D1":  "M15",
        "H12": "M15",
        "H4":  "M5",
        "H1":  "M1",
        "M30": "M1",
        "M15": "M1",
    }

    run_tfs = []

    if args.tf:
        target_tf = args.tf.upper()
        if target_tf in TF_MAP:
            run_tfs.append(target_tf)
        if target_tf in HTF_TO_LTF:
            associated_ltf = HTF_TO_LTF[target_tf]
            if associated_ltf not in run_tfs:
                run_tfs.append(associated_ltf)
        
        if not run_tfs:
            print(f"❌ Error: Timeframe '{args.tf}' is not supported for S10.")
            print(f"Supported LTFs: {list(TF_MAP.keys())}")
            print(f"Supported HTFs: {list(HTF_TO_LTF.keys())}")
            mt5.shutdown()
            return
    else:
        run_tfs = list(TF_MAP.keys())

    for tf_name in run_tfs:
        tf_val = TF_MAP[tf_name]
        trades = backtest_tf(tf_name, tf_val)
        filtered = [t for t in trades if window_start_utc <= t['entry_time'] <= window_end_utc]

        if args.tf:
            filtered = [t for t in filtered if t.get('s10_htf_tf') == args.tf.upper()]

        if args.exclude_cancelled:
            filtered = [t for t in filtered if t['close_type'] not in ('CANCEL', 'PD_FAIL', 'OPEN_PENDING')]

        all_trades.extend([(t.get("s10_htf_tf", tf_name), t) for t in filtered])

        if not filtered:
            continue

        from collections import defaultdict
        htf_groups = defaultdict(list)
        for t in filtered:
            htf_groups[t.get("s10_htf_tf", tf_name)].append(t)

        for htf_name, grp_trades in htf_groups.items():
            total = sum(t['pnl'] for t in grp_trades)
            grand_total += total

            ltf_of_htf = HTF_TO_LTF.get(htf_name, "")
            tf_display = f"{htf_name} ({ltf_of_htf})" if ltf_of_htf else htf_name

            print(f"\n## {tf_display} - Trades in window ({len(grp_trades)} trades)\nTotal P&L: {total:+.2f} USD")
            
            for idx, t in enumerate(grp_trades):
                et = t['entry_time'].strftime('%Y-%m-%d %H:%M')
                ct = t['close_time'].strftime('%Y-%m-%d %H:%M') if t['close_type'] not in ('OPEN', 'OPEN_PENDING') else 'OPEN'
                pnl_s = f'{"+" if t["pnl"]>=0 else ""}{t["pnl"]:.2f}'

                print(f"\n--- Trade #{idx+1} ---")
                print(f"  [{tf_display}] {et} {t['signal']} [{t.get('pattern', 'S10')}]")
                print(f"  Entry  = {t['entry']:.2f} | SL = {t['sl']:.2f} | TP = {t['tp']:.2f}")
                close_label = t['close_type']
                if close_label == 'PD_FAIL':
                    close_label = 'PD_FILL_FAIL' if t.get('pd_result') == 'FAIL' else 'PD_PENDING_FAIL'
                print(f"  Result -> {close_label} @ {t.get('close_price', 0):.2f} [{ct}]  PnL={pnl_s} USD")

                if t.get('cancel_reason'):
                    print(f"  Cancel Reason: {t['cancel_reason']}")

                # Parent & Sweep HTF details
                htf_tf = t.get('s10_htf_tf')
                if htf_tf:
                    parent_h = t.get('s10_parent_high', 0.0)
                    parent_low = t.get('s10_parent_low', 0.0)
                    parent_range = parent_h - parent_low
                    parent_time_unix = t.get('s10_parent_time', 0)
                    sweep_time_unix = t.get('s10_sweep_time', 0)
                    parent_t_str = to_bkk(parent_time_unix).strftime('%Y-%m-%d %H:%M') if parent_time_unix else '?'
                    sweep_t_str = to_bkk(sweep_time_unix).strftime('%d-%m %H:%M') if sweep_time_unix else '?'
                    bar_mode = t.get('s10_bar_mode', '2bar')

                    print(f"  HTF Details:")
                    print(f"    HTF TF = {htf_tf} | Bar Mode = {bar_mode}")
                    print(f"    Parent Bar: High = {parent_h:.2f}, Low = {parent_low:.2f}, Range = {parent_range:.2f} | Time = {parent_t_str}")
                    print(f"    Sweep Time: {sweep_t_str}")

                    m1_p = t.get('s10_m1_price')
                    m1_t = t.get('s10_m1_time')
                    m2_p = t.get('s10_m2_price')
                    m2_t = t.get('s10_m2_time')
                    m3_p = t.get('s10_m3_price')
                    m3_t = t.get('s10_m3_time')
                    print(f"  Models Info:")
                    print(f"    Model 1 (OB.open): {f'{m1_p:.2f}' if m1_p is not None else 'n/a'} @ {m1_t or 'n/a'}")
                    print(f"    Model 2 (FVG 98%): {f'{m2_p:.2f}' if m2_p is not None else 'n/a'} @ {m2_t or 'n/a'}")
                    print(f"    Model 3 (MSS)    : {f'{m3_p:.2f}' if m3_p is not None else 'n/a'} @ {m3_t or 'n/a'}")

                # PD Fibo Plus details (kept for non-skipped strategies if present in old/custom data)
                pd_val = t.get('pd_result')
                if pd_val:
                    fibo_pct = t.get('pd_fibo_pct')
                    pd_round = t.get('pd_round', 1)
                    pd_fibo_str = f" ({fibo_pct:.1f}%)" if fibo_pct is not None else ""
                    print(f"  PD Fibo Plus:")
                    print(f"    PD Result: {pd_val}{pd_fibo_str} [Round {pd_round}]")
                    if t.get('pd_h') is not None and t.get('pd_l') is not None:
                        h_t = to_bkk(t['pd_h_time']).strftime('%d-%m %H:%M') if t.get('pd_h_time') else '?'
                        l_t = to_bkk(t['pd_l_time']).strftime('%d-%m %H:%M') if t.get('pd_l_time') else '?'
                        print(f"    PD Range : H = {t['pd_h']:.2f} [{h_t}] | L = {t['pd_l']:.2f} [{l_t}]")

    print('\n' + '=' * 65)
    print(f'GRAND TOTAL P&L for window: {grand_total:+.2f} USD')
    mt5.shutdown()

if __name__ == '__main__':
    run_backtest()
