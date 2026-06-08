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

# Convert Bangkok (UTC+7) to UTC for MT5 calls
window_start_utc = (window_start_bkk - timedelta(hours=7)).replace(tzinfo=timezone.utc)
window_end_utc   = (window_end_bkk   - timedelta(hours=7)).replace(tzinfo=timezone.utc)

def run_backtest():
    if not mt5.initialize():
        print('MT5 init failed:', mt5.last_error())
        return

    grand_total = 0.0
    all_trades = []

    for tf_name, tf_val in TF_MAP.items():
        trades = backtest_tf(tf_name, tf_val)
        # Filter trades where entry_time falls within the specified UTC window (entry_time is UTC-aware)
        filtered = [t for t in trades if window_start_utc <= t['entry_time'] <= window_end_utc]
        all_trades.extend([(tf_name, t) for t in filtered])
        if not filtered:
            continue
        total = sum(t['pnl'] for t in filtered)
        grand_total += total
        print(f"\n## {tf_name} - Trades in window {window_start_bkk} → {window_end_bkk} ({len(filtered)} trades)\nTotal P&L: {total:+.2f} USD")
        for t in filtered:
            et = t['entry_time'].strftime('%Y-%m-%d %H:%M')
            ct = t['close_time'].strftime('%Y-%m-%d %H:%M') if t['close_type'] != 'OPEN' else 'OPEN'
            print(f"{et} {t['signal']:<4} Entry={t['entry']:.2f} SL={t['sl']:.2f} TP={t['tp']:.2f} -> {t['close_type']:<4} @ {t.get('close_price',0):.2f} [{ct}] PnL={t['pnl']:+.2f} [{t['pattern']}]")

    print('\n' + '='*40)
    print(f'GRAND TOTAL P&L for window: {grand_total:+.2f} USD')
    mt5.shutdown()

if __name__ == '__main__':
    run_backtest()
