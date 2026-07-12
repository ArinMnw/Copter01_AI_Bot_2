import sys
import os
import pandas as pd
import MetaTrader5 as mt5
import argparse
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(r'd:\Project\Copter01_AI_Bot_2'))
import config
from sim_s30_backtest import fetch_bars
import strategy96

parser = argparse.ArgumentParser(description="Backtest S96 Volume Profile PoC Pullback")
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

trades = []
last_trade_idx = -100

# Pre-calculate EMA600 for HTF Trend filter (600 M5 bars = 50 H1 bars)
all_closes = pd.Series([b['close'] for b in all_bars])
ema600_series = all_closes.ewm(span=600, adjust=False).mean()

for i in range(LOOKBACK, len(all_bars) - 1):
    if i - last_trade_idx < 10:
        continue
        
    rates_slice = all_bars[i-LOOKBACK+1 : i+1]
    # H1 EMA50 mapping for HTF Trend Filter
    htf_ctx = None
    if i > LOOKBACK:
        # Pre-calculated EMA600
        ema600 = ema600_series.iloc[i-1] # previous bar EMA
        ema600_prev = ema600_series.iloc[i-11] if (i-11) > 0 else ema600_series.iloc[0]
        
        # If ema is sloping up, trend_up is True
        htf_ctx = {
            "trend_up": ema600 > ema600_prev,
            "trend_down": ema600 < ema600_prev
        }
        
    cfg_s96 = {
        "CONFIRMATION_TYPE": "htf_trend",
        "RSI_FILTER_ENABLED": True,
        "RSI_BUY_MIN": 40.0,
        "RSI_SELL_MAX": 60.0,
        "TIME_FILTER_ENABLED": True,
        "PD_ZONE_FILTER_ENABLED": False,
        "ML_FILTER_ENABLED": False
    }
    
    dt_bkk = datetime.fromtimestamp(rates_slice[-1]['time'])
    sig = strategy96.detect_s96(rates_slice, tf=TF, dt_bkk=dt_bkk, cfg=cfg_s96, htf_ctx=htf_ctx)
    
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
output_csv = "s96_trades.csv"
df = pd.DataFrame(trades)
df.to_csv(output_csv, index=False)
print(f"Saved {len(trades)} trades to {output_csv}")

if len(df) > 0:
    df['time'] = pd.to_datetime(df['time'])
    df['date'] = df['time'].dt.date
    df['month'] = df['time'].dt.strftime('%Y-%m')
    
    # Daily
    daily_records = []
    for d, grp in df.groupby('date'):
        tp = (grp['outcome'] == 'TP').sum()
        sl = (grp['outcome'] == 'SL').sum()
        net = pd.to_numeric(grp['profit']).sum()
        wr = tp / (tp + sl) * 100 if tp + sl > 0 else 0
        daily_records.append({'date': d, 'trades': len(grp), 'win': tp, 'loss': sl, 'net_profit': round(net, 2), 'win_rate': round(wr, 2)})
    pd.DataFrame(daily_records).to_csv('s96_daily.csv', index=False)

    # Monthly
    monthly_records = []
    for m, grp in df.groupby('month'):
        tp = (grp['outcome'] == 'TP').sum()
        sl = (grp['outcome'] == 'SL').sum()
        net = pd.to_numeric(grp['profit']).sum()
        wr = tp / (tp + sl) * 100 if tp + sl > 0 else 0
        monthly_records.append({'month': m, 'trades': len(grp), 'win': tp, 'loss': sl, 'net_profit': round(net, 2), 'win_rate': round(wr, 2)})
    pd.DataFrame(monthly_records).to_csv('s96_monthly.csv', index=False)
    print("Saved s96_daily.csv and s96_monthly.csv")
