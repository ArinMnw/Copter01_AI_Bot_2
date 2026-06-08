import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import config
from sim_s14_backtest import backtest_tf, TF_MAP, to_bkk

# ---------------------------------------------------------------------------
# Argument parsing – allows specifying full start/end datetimes (Bangkok timezone)
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description='Backtest S14 signals for a specific Bangkok datetime window')
parser.add_argument('--start', type=str, required=True,
                    help='Window start (YYYY-MM-DDTHH:MM or YYYY-MM-DD HH:MM) in Bangkok timezone')
parser.add_argument('--end', type=str, required=True,
                    help='Window end (YYYY-MM-DDTHH:MM or YYYY-MM-DD HH:MM) in Bangkok timezone')
parser.add_argument('--tf', type=str, required=False,
                    help='Timeframe name to backtest (e.g., M5). If omitted, all timeframes are tested')
args = parser.parse_args()

# Parameters
SYMBOL = config.SYMBOL
VOLUME = 0.01

# Helper to parse datetime strings in two common formats
def parse_bkk_dt(dt_str: str) -> datetime:
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    raise ValueError(f'Invalid datetime format: {dt_str}. Use YYYY-MM-DDTHH:MM or YYYY-MM-DD HH:MM')

window_start_bkk = parse_bkk_dt(args.start)
window_end_bkk   = parse_bkk_dt(args.end)

if window_end_bkk < window_start_bkk:
    raise ValueError('End datetime must be after start datetime')

# Convert Bangkok (UTC+7) wall time to UTC timezone representation (without shifting) for comparison
window_start_utc = window_start_bkk.replace(tzinfo=timezone.utc)
window_end_utc   = window_end_bkk.replace(tzinfo=timezone.utc)

def run_backtest():
    if not mt5.initialize():
        print('MT5 init failed:', mt5.last_error())
        return

    grand_total = 0.0
    all_trades = []

    # Determine which timeframes to process
    tf_items = [(args.tf, TF_MAP[args.tf])] if args.tf else TF_MAP.items()
    for tf_name, tf_val in tf_items:
        trades = backtest_tf(tf_name, tf_val)
        # Filter trades where entry_time falls within the specified UTC window (entry_time is UTC-aware)
        filtered = [t for t in trades if window_start_utc <= t['entry_time'] <= window_end_utc]
        all_trades.extend([(tf_name, t) for t in filtered])
        if not filtered:
            continue
        total = sum(t['pnl'] for t in filtered)
        grand_total += total
        print(f"\n## {tf_name} - Trades in window {window_start_bkk} → {window_end_bkk} ({len(filtered)} trades)\nTotal P&L: {total:+.2f} USD")
        for idx, t in enumerate(filtered):
            et = t['entry_time'].strftime('%Y-%m-%d %H:%M')
            ct = t['close_time'].strftime('%Y-%m-%d %H:%M') if t['close_type'] != 'OPEN' else 'OPEN'
            # Swing reference info
            ref_price = t.get('ref_low', t.get('ref_high', None))
            ref_src   = t.get('ref_source', '?')
            ref_ts    = t.get('ref_time', None)
            ref_time_s = to_bkk(ref_ts).strftime('%m-%d %H:%M') if ref_ts else '?'
            ref_str   = f"Swing={ref_src} @{ref_price:.2f} [{ref_time_s}]" if ref_price else ""
            pd_val = t.get('pd_result')
            fibo_pct = t.get('pd_fibo_pct')
            pd_round = t.get('pd_round', 1)
            pd_fibo_str = f" [Round {pd_round}] ({fibo_pct:.1f}%)" if fibo_pct is not None else f" [Round {pd_round}]"
            pd_str    = f"PD: {pd_val}{pd_fibo_str}" if pd_val else ""
            
            pd_hl_str = ""
            if pd_val and t.get('pd_h') is not None and t.get('pd_l') is not None:
                h_t = to_bkk(t['pd_h_time']).strftime('%m-%d %H:%M') if t.get('pd_h_time') else '?'
                l_t = to_bkk(t['pd_l_time']).strftime('%m-%d %H:%M') if t.get('pd_l_time') else '?'
                pd_hl_str = f"  PD Swing: H={t['pd_h']:.2f} [{h_t}] | L={t['pd_l']:.2f} [{l_t}]"
                
            sub_pat   = t.get('sub_pattern', '?')
            pat_detail_str = ""
            if "sweep" in sub_pat and t.get("sweep_bar_time") is not None:
                sw_t = to_bkk(t["sweep_bar_time"]).strftime('%m-%d %H:%M')
                sw_p = t["sweep_bar_price"]
                pat_detail_str = f"  Sweep Bar: [{sw_t}] Price={sw_p:.2f}"
            elif "engulf" in sub_pat and t.get("engulf_bar_time") is not None:
                eg_t = to_bkk(t["engulf_bar_time"]).strftime('%m-%d %H:%M')
                eg_p = t["engulf_bar_price"]
                eg_c = t["engulf_close"]
                htf_tf = t.get("htf_tf", "?")
                htf_str = ""
                if t.get("htf_bar_time") is not None:
                    ht_t = to_bkk(t["htf_bar_time"]).strftime('%m-%d %H:%M')
                    ho = t["htf_bar_open"]
                    hc = t["htf_bar_close"]
                    htf_str = f"\n  HTF Bar ({htf_tf}): [{ht_t}] O={ho:.2f}, C={hc:.2f}"
                pat_detail_str = f"  Engulf Bar: [{eg_t}] Price={eg_p:.2f}, Close={eg_c:.2f}{htf_str}"
                
            rsi_ref   = t.get('rsi_at_ref', 0)
            rsi_rej   = t.get('rsi_at_rej', 0)
            rsi_str   = f"RSI: ref={rsi_ref:.1f} -> rej={rsi_rej:.1f} (diff={abs(rsi_rej-rsi_ref):.1f})" if rsi_ref else ""
            print(f"\n--- Trade #{idx+1} ---")
            print(f"  {et} {t['signal']} [{sub_pat}]")
            print(f"  Entry  = {t['entry']:.2f} | SL = {t['sl']:.2f} | TP = {t['tp']:.2f}")
            print(f"  Fill   = {et}")
            print(f"  Result -> {t['close_type']} @ {t.get('close_price',0):.2f} [{ct}]  PnL={t['pnl']:+.2f}")
            print(f"  {ref_str}")
            print(f"  {rsi_str}")
            if pat_detail_str:
                print(pat_detail_str)
            if pd_str:
                print(f"  {pd_str}")
                if pd_hl_str:
                    print(pd_hl_str)

    print('\n' + '='*40)
    print(f'GRAND TOTAL P&L for window: {grand_total:+.2f} USD')
    mt5.shutdown()

if __name__ == '__main__':
    run_backtest()
