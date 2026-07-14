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

def run_single(entry_bars, htf_bars, cfg, days, spread):
    trades = []
    last_trade_idx = -100
    all_closes = pd.Series([b['close'] for b in entry_bars])
    ema600_series = all_closes.ewm(span=600, adjust=False).mean()
    
    for i in range(100, len(entry_bars) - 1):
        if i - last_trade_idx < 10:
            continue
            
        rates_slice = entry_bars[i-100+1 : i+1]
        
        # H1 EMA50 mapping for HTF Trend Filter
        htf_ctx = None
        if i > 100:
            ema600 = ema600_series.iloc[i-1]
            ema600_prev = ema600_series.iloc[i-11] if (i-11) > 0 else ema600_series.iloc[0]
            htf_ctx = {
                "trend_up": ema600 > ema600_prev,
                "trend_down": ema600 < ema600_prev
            }
            
        sig = strategy96.detect_s96(rates_slice, tf="M5", dt_bkk=datetime.fromtimestamp(rates_slice[-1]['time']), cfg=cfg, htf_ctx=htf_ctx)
        
        if sig and sig.get("signal") in ["BUY", "SELL"]:
            direction = sig["signal"]
            entry = sig["entry"]
            sl = sig["sl"]
            tp = sig["tp"]
            fill_time = entry_bars[i]['time']
            
            outcome = "OPEN"
            exit_price = 0
            exit_time = 0
            for j in range(i+1, len(entry_bars)):
                h = entry_bars[j]['high']
                l = entry_bars[j]['low']
                if direction == "BUY":
                    if l <= sl:
                        outcome, exit_price = "SL", sl
                        exit_time = entry_bars[j]['time']
                        break
                    elif h >= tp:
                        outcome, exit_price = "TP", tp
                        exit_time = entry_bars[j]['time']
                        break
                else:
                    if h >= sl:
                        outcome, exit_price = "SL", sl
                        exit_time = entry_bars[j]['time']
                        break
                    elif l <= tp:
                        outcome, exit_price = "TP", tp
                        exit_time = entry_bars[j]['time']
                        break
                        
            if outcome != "OPEN":
                last_trade_idx = i
                diff = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
                pnl = (diff - spread) * 1.0
                trades.append({
                    "fill_time_ts": fill_time,
                    "exit_time_ts": exit_time,
                    "signal": direction,
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "diff_usd_per_001lot": round(diff, 4),
                    "spread": spread,
                    "outcome": outcome,
                    "lot": 0.01,
                    "pnl_usd": round(pnl, 2)
                })
    return trades

def run_main():
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

    cfg_s96 = {
        "CONFIRMATION_TYPE": "htf_trend",
        "RSI_FILTER_ENABLED": True,
        "RSI_BUY_MIN": 40.0,
        "RSI_SELL_MAX": 60.0,
        "TIME_FILTER_ENABLED": True,
        "PD_ZONE_FILTER_ENABLED": False,
        "ML_FILTER_ENABLED": False
    }

    trades = run_single(all_bars, None, cfg_s96, DAYS, SPREAD)

    # Save to CSV
    output_csv = "s96_trades.csv"
    trades_converted = []
    for t in trades:
        signal_time = datetime.fromtimestamp(t["fill_time_ts"])
        exit_time = datetime.fromtimestamp(t["exit_time_ts"])
        trades_converted.append({
            'time': signal_time.strftime('%Y-%m-%d %H:%M'),
            'exit_time': exit_time.strftime('%Y-%m-%d %H:%M'),
            'dir': t["signal"],
            'entry': round(t["entry"], 2),
            'sl': round(t["sl"], 2),
            'tp': round(t["tp"], 2),
            'outcome': t["outcome"],
            'profit': round((t["diff_usd_per_001lot"] - t["spread"]) * 1.0, 2)
        })
    df = pd.DataFrame(trades_converted)
    df.to_csv(output_csv, index=False)
    print(f"Saved {len(df)} trades to {output_csv}")

    if len(df) > 0:
        df['time'] = pd.to_datetime(df['time'])
        df['date'] = df['time'].dt.date
        df['month'] = df['time'].dt.strftime('%Y-%m')
        
        # Daily
        daily_records = []
        for d, grp in df.groupby('date'):
            tp_cnt = (grp['outcome'] == 'TP').sum()
            sl_cnt = (grp['outcome'] == 'SL').sum()
            net = pd.to_numeric(grp['profit']).sum()
            wr = tp_cnt / (tp_cnt + sl_cnt) * 100 if tp_cnt + sl_cnt > 0 else 0
            daily_records.append({'date': d, 'trades': len(grp), 'win': tp_cnt, 'loss': sl_cnt, 'net_profit': round(net, 2), 'win_rate': round(wr, 2)})
        pd.DataFrame(daily_records).to_csv('s96_daily.csv', index=False)

        # Monthly
        monthly_records = []
        for m, grp in df.groupby('month'):
            tp_cnt = (grp['outcome'] == 'TP').sum()
            sl_cnt = (grp['outcome'] == 'SL').sum()
            net = pd.to_numeric(grp['profit']).sum()
            wr = tp_cnt / (tp_cnt + sl_cnt) * 100 if tp_cnt + sl_cnt > 0 else 0
            monthly_records.append({'month': m, 'trades': len(grp), 'win': tp_cnt, 'loss': sl_cnt, 'net_profit': round(net, 2), 'win_rate': round(wr, 2)})
        pd.DataFrame(monthly_records).to_csv('s96_monthly.csv', index=False)
        print("Saved s96_daily.csv and s96_monthly.csv")

if __name__ == "__main__":
    run_main()
