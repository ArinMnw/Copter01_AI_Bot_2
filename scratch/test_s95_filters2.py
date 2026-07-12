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

trades = []

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
    
    rates = slice_
    atr = sum([max(r["high"] - r["low"], abs(r["high"] - rates[j-1]["close"]), abs(r["low"] - rates[j-1]["close"])) for j, r in enumerate(rates[-15:]) if j > 0]) / 14.0
    
    last_candle = rates[-1]
    total_range = last_candle['high'] - last_candle['low']
    body_range = abs(last_candle['close'] - last_candle['open'])
    wick_pct = max(last_candle['high'] - max(last_candle['open'], last_candle['close']), min(last_candle['open'], last_candle['close']) - last_candle['low']) / total_range if total_range > 0 else 0
    
    entry, sl, tp = sig['entry'], sig['sl'], sig['tp']
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
        trades.append({
            'outcome': outcome,
            'profit': usd,
            'atr': atr,
            'range': total_range,
            'body_pct': body_range/total_range if total_range>0 else 0,
            'wick_pct': wick_pct
        })

df = pd.DataFrame(trades)
print("Total Trades:", len(df))
print("Win Rate:", len(df[df['outcome']=='TP'])/len(df)*100, "%")
print("Net Profit:", df['profit'].sum())

print("\n--- Analyzing SL vs TP Properties ---")
print("TP Average Wick Pct:", df[df['outcome']=='TP']['wick_pct'].mean())
print("SL Average Wick Pct:", df[df['outcome']=='SL']['wick_pct'].mean())
print("TP Average Body Pct:", df[df['outcome']=='TP']['body_pct'].mean())
print("SL Average Body Pct:", df[df['outcome']=='SL']['body_pct'].mean())
print("TP Average Range/ATR:", (df[df['outcome']=='TP']['range']/df[df['outcome']=='TP']['atr']).mean())
print("SL Average Range/ATR:", (df[df['outcome']=='SL']['range']/df[df['outcome']=='SL']['atr']).mean())

mt5.shutdown()
