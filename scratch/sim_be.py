import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'strategy', 's20.13')))

# We will run the strategy over the data and for each trade, track bar-by-bar
import config
from strategy20_13 import strategy_20_13

if not mt5.initialize():
    sys.exit()

sym = "XAUUSD.iux"
rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 1000) # Get enough bars
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

active_mode = getattr(config, "S20_13_ACTIVE_MODE", 2.6)

trades = []
for i in range(30, len(df)):
    # Feed slice to strategy
    slice_df = df.iloc[:i+1]
    rates_slice = slice_df.to_dict('records')
    # Strategy expects unix timestamp
    for r in rates_slice:
        r['time'] = r['time'].timestamp()
        
    res = strategy_20_13(rates_slice, tf="H1")
    if res['signal'] in ['BUY', 'SELL']:
        # Found a trade!
        entry_time = slice_df.iloc[-1]['time']
        entry_price = res['entry']
        tp = res['tp']
        sl = res['sl']
        signal = res['signal']
        
        # Calculate SD 1.5 level
        # Fuel used for TP was ActiveMode (2.6). SD 1.5 fuel is (1.5 / 2.6) of TP distance
        tp_dist = abs(tp - entry_price) # This is not perfectly fuel because of sweep base, but close enough.
        
        # Let's re-extract exact fuel
        reason = res['reason'] # "Sweep X | Engulf | TP Y"
        # The true fuel distance from base is TP - Base.
        # But for breakeven, we just measure from ENTRY!
        # If entry is at base, then 1.5/2.6 of (TP - Entry) is the 1.5 SD mark.
        sd15_dist = tp_dist * (1.5 / 2.6)
        
        if signal == 'BUY':
            be_trigger = entry_price + sd15_dist
        else:
            be_trigger = entry_price - sd15_dist
            
        trades.append({
            "entry_time": entry_time,
            "signal": signal,
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "be_trigger": be_trigger,
            "start_idx": i
        })

# Now evaluate each trade
results = []
for t in trades:
    status = "OPEN"
    close_price = 0
    close_time = None
    sl = t['sl']
    be_active = False
    
    for j in range(t['start_idx'] + 1, len(df)):
        bar = df.iloc[j]
        
        # Check TP/SL for BUY
        if t['signal'] == 'BUY':
            if bar['high'] >= t['tp']:
                status = "WIN"
                close_price = t['tp']
                close_time = bar['time']
                break
            if bar['low'] <= sl:
                status = "LOSS" if not be_active else "BE"
                close_price = sl
                close_time = bar['time']
                break
            # Check BE trigger
            if not be_active and bar['high'] >= t['be_trigger']:
                be_active = True
                sl = t['entry'] # Move SL to entry
                
        # Check TP/SL for SELL
        if t['signal'] == 'SELL':
            if bar['low'] <= t['tp']:
                status = "WIN"
                close_price = t['tp']
                close_time = bar['time']
                break
            if bar['high'] >= sl:
                status = "LOSS" if not be_active else "BE"
                close_price = sl
                close_time = bar['time']
                break
            # Check BE trigger
            if not be_active and bar['low'] <= t['be_trigger']:
                be_active = True
                sl = t['entry'] # Move SL to entry

    results.append({
        "time": t['entry_time'],
        "signal": t['signal'],
        "status": status,
        "be_hit": be_active
    })

# Summary
wins = [r for r in results if r['status'] == 'WIN']
losses = [r for r in results if r['status'] == 'LOSS']
bes = [r for r in results if r['status'] == 'BE']
opens = [r for r in results if r['status'] == 'OPEN']

print(f"Total Trades: {len(results)}")
print(f"WIN (SD 2.6): {len(wins)}")
print(f"BE (Hit 1.5, then dropped to Entry): {len(bes)}")
print(f"LOSS (Hit SL before 1.5): {len(losses)}")
print(f"OPEN: {len(opens)}")

# Were any original wins turned into BE?
mt5.shutdown()
