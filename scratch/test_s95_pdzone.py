import sys
import os
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime

sys.path.append(os.path.abspath('.'))
import config
from sim_s30_backtest import fetch_bars
import strategy95

config.mt5_initialize(mt5)
all_bars = fetch_bars('XAUUSD.iux', 'M5', 90, extra_bars=400)
if all_bars is None or len(all_bars) == 0:
    sys.exit()

all_closes = pd.Series([b['close'] for b in all_bars])
ema600_series = all_closes.ewm(span=600, adjust=False).mean()

cfg_s95 = {
    "CONFIRMATION_TYPE": "htf_trend",
    "RSI_FILTER_ENABLED": True,
    "RSI_BUY_MIN": 40.0,
    "RSI_SELL_MAX": 60.0,
    "TIME_FILTER_ENABLED": True
}

trades_orig = []
trades_pd = []

for i in range(200, len(all_bars)-1):
    slice_ = all_bars[i-199:i+1]
    dt_bkk = datetime.fromtimestamp(slice_[-1]['time'])
    
    sig = strategy95.detect_s95(slice_, tf='M5', dt_bkk=dt_bkk, cfg=cfg_s95)
    if not sig or sig.get('signal') not in ['BUY', 'SELL']: continue
    
    ema600 = ema600_series.iloc[i-1]
    ema600_prev = ema600_series.iloc[i-11]
    trend_up = ema600 > ema600_prev
    
    if sig['signal'] == 'BUY' and not trend_up: continue
    if sig['signal'] == 'SELL' and trend_up: continue
    
    recent_bars = all_bars[i-99:i+1]
    highest = max([b['high'] for b in recent_bars])
    lowest = min([b['low'] for b in recent_bars])
    eq = (highest + lowest) / 2.0
    
    entry = sig['entry']
    
    pass_pd = False
    if sig['signal'] == 'BUY' and entry <= eq: pass_pd = True
    if sig['signal'] == 'SELL' and entry >= eq: pass_pd = True
    
    sl, tp = sig['sl'], sig['tp']
    outcome = 'OPEN'
    exit_p = 0
    for j in range(i+1, len(all_bars)):
        h, l = all_bars[j]['high'], all_bars[j]['low']
        if sig['signal'] == 'BUY':
            if l <= sl: outcome, exit_p = 'SL', sl; break
            elif h >= tp: outcome, exit_p = 'TP', tp; break
        else:
            if h >= sl: outcome, exit_p = 'SL', sl; break
            elif l <= tp: outcome, exit_p = 'TP', tp; break
            
    if outcome != 'OPEN':
        diff = (exit_p - entry) if sig['signal']=='BUY' else (entry - exit_p)
        usd = diff - 0.20
        trades_orig.append(usd)
        if pass_pd: trades_pd.append(usd)

def print_stats(name, t_list):
    if not t_list: return
    win = len([t for t in t_list if t > 0])
    loss = len([t for t in t_list if t <= 0])
    wr = win/len(t_list)*100
    net = sum(t_list)
    print(f"{name}: {len(t_list)} trades, WR: {wr:.2f}%, Net: {net:.2f} USD")

print_stats("Original", trades_orig)
print_stats("PD Zone Filter", trades_pd)

mt5.shutdown()
