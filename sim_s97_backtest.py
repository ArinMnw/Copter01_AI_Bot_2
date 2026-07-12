import sys
import os
import pandas as pd
import MetaTrader5 as mt5
import argparse
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(r'd:\Project\Copter01_AI_Bot_2'))
import config
from sim_s30_backtest import fetch_bars
import strategy97

parser = argparse.ArgumentParser(description="Backtest S97 Sweep+PoC")
parser.add_argument("--days", type=int, default=30, help="Number of days to backtest (if start/end not provided)")
parser.add_argument("--start", type=str, help="Start date in YYYY-MM-DD format (e.g. 2026-05-01)")
parser.add_argument("--end", type=str, help="End date in YYYY-MM-DD format (e.g. 2026-06-01)")
args = parser.parse_args()

SYMBOL = "XAUUSD.iux"
TF = "M5"
DAYS = args.days
SPREAD = 0.20
LOOKBACK = 100

if not config.mt5_initialize(mt5):
    print("MT5 init failed")
    sys.exit(1)

if args.start and args.end:
    start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end, "%Y-%m-%d") + timedelta(days=1)
    
    # We need timezone info (using UTC+7 BKK logic)
    import pytz
    bkk = pytz.timezone("Asia/Bangkok")
    start_dt = bkk.localize(start_dt)
    end_dt = bkk.localize(end_dt)
    
    all_bars = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M5, start_dt, end_dt)
else:
    all_bars = fetch_bars(SYMBOL, TF, DAYS, extra_bars=200)
    
mt5.shutdown()

if all_bars is None or len(all_bars) == 0:
    print("Failed to fetch")
    sys.exit(1)

print(f"Loaded {len(all_bars)} bars")

trades = []
last_trade_idx = -100

for i in range(LOOKBACK, len(all_bars) - 1):
    if i - last_trade_idx < 10:
        continue
        
    rates_slice = all_bars[i-LOOKBACK+1 : i+1]
    sig = strategy97.detect_s97(rates_slice, tf="")
    
    if sig and sig.get("signal") in ["BUY", "SELL"]:
        direction = sig["signal"]
        entry = sig["entry"]
        sl = sig["sl"]
        tp = sig["tp"]
        signal_time = datetime.fromtimestamp(all_bars[i]['time'])
        
        # Forward simulate
        outcome = "OPEN"
        exit_price = 0
        exit_time = None
        for j in range(i+1, len(all_bars)):
            h = all_bars[j]['high']
            l = all_bars[j]['low']
            if direction == "BUY":
                if l <= sl:
                    outcome, exit_price = "SL", sl
                    exit_time = datetime.fromtimestamp(all_bars[j]['time'])
                    break
                elif h >= tp:
                    outcome, exit_price = "TP", tp
                    exit_time = datetime.fromtimestamp(all_bars[j]['time'])
                    break
            else:
                if h >= sl:
                    outcome, exit_price = "SL", sl
                    exit_time = datetime.fromtimestamp(all_bars[j]['time'])
                    break
                elif l <= tp:
                    outcome, exit_price = "TP", tp
                    exit_time = datetime.fromtimestamp(all_bars[j]['time'])
                    break
                    
        if outcome != "OPEN":
            last_trade_idx = i
            diff = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
            # $ per 0.01 lot
            usd = diff - SPREAD
            trades.append({
                'time': signal_time.strftime('%Y-%m-%d %H:%M'),
                'exit_time': exit_time.strftime('%Y-%m-%d %H:%M') if exit_time else '-',
                'dir': direction,
                'entry': round(entry, 2),
                'sl': round(sl, 2),
                'tp': round(tp, 2),
                'outcome': outcome,
                'profit': round(usd, 2)
            })

# Save to CSV
output_csv = "s97_trades.csv"
df = pd.DataFrame(trades)
df.to_csv(output_csv, index=False)
print(f"Saved {len(trades)} trades to {output_csv}")

if not trades:
    print("No trades")
else:
    win = sum(1 for t in trades if t['outcome'] == 'TP')
    total = sum(t['profit'] for t in trades)
    wr = win / len(trades) * 100
    avg_d = total / DAYS
    avg_m = avg_d * 22
    
    print(f"--- S97 (Sweep + PoC Fusion) ---")
    print(f"Trades: {len(trades)}")
    print(f"Win Rate: {wr:.2f}%")
    print(f"Total Net: ${total:.2f} (per 0.01 lot)")
    print(f"Avg $/day: ${avg_d:.2f}")
    print(f"Avg $/month: ${avg_m:.2f}")
