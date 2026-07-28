import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys

sys.path.append('d:\\Project\\Copter01_AI_Bot_2')
sys.path.append('d:\\Project\\Copter01_AI_Bot_2\\strategy\\s20.13')
from strategy20_13_17 import strategy_20_13_17

mt5.initialize()
symbol = "XAUUSD.iux"

# 150 days * 24 H1 bars = 3600 bars. Let's get 5000 bars just in case.
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 5000)
if rates is None or len(rates) == 0:
    print("FAILED TO FETCH RATES FROM MT5!")
    mt5.shutdown()
    sys.exit(1)

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
print(f"Loaded {len(df)} bars from {df.iloc[0]['time']} to {df.iloc[-1]['time']}")

trades = []
position = None # {'side': 'BUY'/'SELL', 'entry': price, 'sl': sl, 'tp': tp, 'time': time}

for i in range(50, len(rates)):
    cur_time = df.iloc[i]['time'] # UTC time
    # Check if existing position hits TP or SL
    if position is not None:
        high = df.iloc[i]['high']
        low = df.iloc[i]['low']
        
        if position['side'] == 'BUY':
            if low <= position['sl']:
                pnl = (position['sl'] - position['entry']) * 100 # $ per lot or point
                trades.append({'time': position['time'], 'close_time': cur_time, 'side': 'BUY', 'res': 'SL', 'pnl': -1200})
                position = None
            elif high >= position['tp']:
                trades.append({'time': position['time'], 'close_time': cur_time, 'side': 'BUY', 'res': 'TP', 'pnl': 1500})
                position = None
        elif position['side'] == 'SELL':
            if high >= position['sl']:
                trades.append({'time': position['time'], 'close_time': cur_time, 'side': 'SELL', 'res': 'SL', 'pnl': -1200})
                position = None
            elif low <= position['tp']:
                trades.append({'time': position['time'], 'close_time': cur_time, 'side': 'SELL', 'res': 'TP', 'pnl': 1500})
                position = None

    # If no position, check for signal
    if position is None:
        slice_rates = rates[i-50:i+1]
        res = strategy_20_13_17(slice_rates, tf='H1')
        if res.get('signal') in ['BUY', 'SELL']:
            position = {
                'side': res['signal'],
                'entry': res['entry'],
                'sl': res['sl'],
                'tp': res['tp'],
                'time': cur_time
            }

mt5.shutdown()

df_trades = pd.DataFrame(trades)
if len(df_trades) == 0:
    print("NO TRADES GENERATED!")
    sys.exit(0)

wins = len(df_trades[df_trades['res'] == 'TP'])
losses = len(df_trades[df_trades['res'] == 'SL'])
wr = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
net_profit = df_trades['pnl'].sum()

print("\n=== VERSION 17 BACKTEST RESULTS ===")
print(f"Total Trades: {len(df_trades)}")
print(f"Wins: {wins}, Losses: {losses}")
print(f"Win Rate: {wr:.2f}%")
print(f"Net Profit: ${net_profit:,.2f}")

# Check Sniper Rule
# Notice that Sniper Rule times are given in BKK time:
# 2026-07-16 23:00 BKK -> 16:00 UTC
# 2026-07-17 21:00 BKK -> 14:00 UTC
# 2026-07-17 23:00 BKK -> 16:00 UTC
sniper_utc = [
    pd.to_datetime('2026-07-16 16:00:00'),
    pd.to_datetime('2026-07-17 14:00:00'),
    pd.to_datetime('2026-07-17 16:00:00')
]

print("\n--- SNIPER RULE CHECK ---")
all_passed = True
for st in sniper_utc:
    match = df_trades[df_trades['time'] == st]
    bkk_str = (st + timedelta(hours=7)).strftime('%Y-%m-%d %H:%M')
    if len(match) > 0:
        print(f"[{bkk_str}] PASSED (Side: {match.iloc[0]['side']}, Res: {match.iloc[0]['res']})")
    else:
        print(f"[{bkk_str}] FAILED / MISSING!")
        all_passed = False

if all_passed:
    print("ALL SNIPER TRADES PASSED SUCCESSFULLLY!")
else:
    print("WARNING: SOME SNIPER TRADES MISSING!")
