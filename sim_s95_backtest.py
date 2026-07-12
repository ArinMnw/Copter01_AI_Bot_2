import pandas as pd
import MetaTrader5 as mt5
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(r'd:\Project\Copter01_AI_Bot_2'))
import config
from sim_s30_backtest import fetch_bars
import strategy95

import argparse

def main():
    parser = argparse.ArgumentParser(description="Backtest S95 Liquidity Sweep")
    parser.add_argument("--days", type=int, default=30, help="Number of days to backtest")
    args = parser.parse_args()

    if not config.mt5_initialize(mt5):
        print("MT5 init failed")
        return
        
    SYMBOL = "XAUUSD.iux"
    TF = "M5"
    DAYS = args.days
    SPREAD = 0.20
    LOOKBACK = 200
    
    all_bars = fetch_bars(SYMBOL, TF, DAYS, extra_bars=300)
    mt5.shutdown()
    
    if len(all_bars) == 0: return
    
    # Pre-calculate EMA600 (approx H1 EMA50)
    all_closes = pd.Series([b['close'] for b in all_bars])
    ema600_series = all_closes.ewm(span=600, adjust=False).mean()
    
    trades = []
    last_trade_idx = -100
    
    for i in range(LOOKBACK, len(all_bars) - 1):
        if i - last_trade_idx < 10: continue
            
        rates_slice = all_bars[i-LOOKBACK+1 : i+1]
        # Extract dt_bkk from the last bar in the slice
        dt_bkk = datetime.fromtimestamp(rates_slice[-1]['time'])
        
        # Setup config for S95
        cfg_s95 = {
            "CONFIRMATION_TYPE": "htf_trend",
            "RSI_FILTER_ENABLED": True,
            "RSI_BUY_MIN": 40.0,
            "RSI_SELL_MAX": 60.0,
            "TIME_FILTER_ENABLED": True,
            "PD_ZONE_FILTER_ENABLED": True,
            "ML_FILTER_ENABLED": True
        }
        
        # Original S95
        sig = strategy95.detect_s95(rates_slice, tf=TF, dt_bkk=dt_bkk, cfg=cfg_s95)
        if not sig or sig.get("signal") not in ["BUY", "SELL"]:
            continue
            
        # Check HTF Trend
        ema600 = ema600_series.iloc[i-1]
        ema600_prev = ema600_series.iloc[i-11]
        trend_up = ema600 > ema600_prev
        trend_down = ema600 < ema600_prev
        
        direction = sig["signal"]
        
        # Apply HTF Filter: only trade in direction of H1 trend
        if direction == "BUY" and not trend_up: continue
        if direction == "SELL" and not trend_down: continue
            
        entry = sig["entry"]
        sl = sig["sl"]
        tp = sig["tp"]
        
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
            signal_time = datetime.fromtimestamp(rates_slice[-1]['time'])
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
            
    win = len([t for t in trades if t['profit'] > 0])
    loss = len([t for t in trades if t['profit'] <= 0])
    total = len(trades)
    wr = win/total*100 if total > 0 else 0
    net = sum([t['profit'] for t in trades])
    
    # Create dataframe for trades like S96
    df = pd.DataFrame(trades)
    if len(df) > 0:
        df.to_csv("s95_trades.csv", index=False)
        print(f"Saved {len(df)} trades to s95_trades.csv")
        
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
        pd.DataFrame(daily_records).to_csv('s95_daily.csv', index=False)

        # Monthly
        monthly_records = []
        for m, grp in df.groupby('month'):
            tp = (grp['outcome'] == 'TP').sum()
            sl = (grp['outcome'] == 'SL').sum()
            net = pd.to_numeric(grp['profit']).sum()
            wr = tp / (tp + sl) * 100 if tp + sl > 0 else 0
            monthly_records.append({'month': m, 'trades': len(grp), 'win': tp, 'loss': sl, 'net_profit': round(net, 2), 'win_rate': round(wr, 2)})
        pd.DataFrame(monthly_records).to_csv('s95_monthly.csv', index=False)
        print("Saved s95_daily.csv and s95_monthly.csv")

if __name__ == "__main__":
    main()
