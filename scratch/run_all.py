import sys
import os
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime

sys.path.append(os.path.abspath('.'))
import config
from sim_s30_backtest import fetch_bars
import strategy95
import strategy96

config.mt5_initialize(mt5)
days_list = [30, 60, 90, 120, 150, 180]

print('Day\tS95_Trades\tS95_WR\tS95_Net\tS96_Trades\tS96_WR\tS96_Net')
for d in days_list:
    # Fetch data
    all_bars = fetch_bars('XAUUSD.iux', 'M5', d, extra_bars=400)
    if all_bars is None or len(all_bars) == 0: continue
    
    all_closes = pd.Series([b['close'] for b in all_bars])
    ema600_series = all_closes.ewm(span=600, adjust=False).mean()
    
    # Run S95
    s95_trades = []
    last_idx95 = -100
    for i in range(200, len(all_bars)-1):
        if i - last_idx95 < 10: continue
        slice_ = all_bars[i-199:i+1]
        dt_bkk = datetime.fromtimestamp(slice_[-1]['time'])
        sig = strategy95.detect_s95(slice_, tf='M5', dt_bkk=dt_bkk)
        if not sig or sig.get('signal') not in ['BUY', 'SELL']: continue
        
        # HTF
        ema600 = ema600_series.iloc[i-1]
        ema600_prev = ema600_series.iloc[i-11]
        trend_up = ema600 > ema600_prev
        if sig['signal'] == 'BUY' and not trend_up: continue
        if sig['signal'] == 'SELL' and trend_up: continue
        
        entry, sl, tp = sig['entry'], sig['sl'], sig['tp']
        outcome = 'OPEN'
        for j in range(i+1, len(all_bars)):
            h, l = all_bars[j]['high'], all_bars[j]['low']
            if sig['signal'] == 'BUY':
                if l <= sl: outcome = 'SL'; exit_p = sl; break
                elif h >= tp: outcome = 'TP'; exit_p = tp; break
            else:
                if h >= sl: outcome = 'SL'; exit_p = sl; break
                elif l <= tp: outcome = 'TP'; exit_p = tp; break
        if outcome != 'OPEN':
            last_idx95 = i
            diff = (exit_p - entry) if sig['signal']=='BUY' else (entry - exit_p)
            s95_trades.append(diff - 0.20)
            
    s95_wr = len([t for t in s95_trades if t>0])/len(s95_trades)*100 if s95_trades else 0
    s95_net = sum(s95_trades)
    
    # Run S96
    s96_trades = []
    last_idx96 = -100
    cfg_s96 = {'CONFIRMATION_TYPE':'htf_trend', 'RSI_FILTER_ENABLED':True, 'RSI_BUY_MIN':40.0, 'RSI_SELL_MAX':60.0, 'TIME_FILTER_ENABLED':True}
    for i in range(100, len(all_bars)-1):
        if i - last_idx96 < 10: continue
        slice_ = all_bars[i-99:i+1]
        dt_bkk = datetime.fromtimestamp(slice_[-1]['time'])
        
        ema600 = ema600_series.iloc[i-1]
        ema600_prev = ema600_series.iloc[i-11]
        htf = {'trend_up': ema600 > ema600_prev, 'trend_down': ema600 < ema600_prev}
        
        sig = strategy96.detect_s96(slice_, tf='M5', dt_bkk=dt_bkk, cfg=cfg_s96, htf_ctx=htf)
        if not sig or sig.get('signal') not in ['BUY', 'SELL']: continue
        
        entry, sl, tp = sig['entry'], sig['sl'], sig['tp']
        outcome = 'OPEN'
        for j in range(i+1, len(all_bars)):
            h, l = all_bars[j]['high'], all_bars[j]['low']
            if sig['signal'] == 'BUY':
                if l <= sl: outcome = 'SL'; exit_p = sl; break
                elif h >= tp: outcome = 'TP'; exit_p = tp; break
            else:
                if h >= sl: outcome = 'SL'; exit_p = sl; break
                elif l <= tp: outcome = 'TP'; exit_p = tp; break
        if outcome != 'OPEN':
            last_idx96 = i
            diff = (exit_p - entry) if sig['signal']=='BUY' else (entry - exit_p)
            # S96 risk is standard, just map pip diff to $
            s96_trades.append((diff - 0.20) * 100)
            
    s96_wr = len([t for t in s96_trades if t>0])/len(s96_trades)*100 if s96_trades else 0
    s96_net = sum(s96_trades)
    
    print(f'{d}\t{len(s95_trades)}\t{s95_wr:.2f}%\t\t{len(s96_trades)}\t{s96_wr:.2f}%\t')

mt5.shutdown()
