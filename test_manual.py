import pandas as pd
import datetime
import MetaTrader5 as mt5
import re

if not mt5.initialize():
    print('MT5 init failed')
    exit()

with open('docs/allin4s/Full Trading/full_trading.md', 'r', encoding='utf-8') as f:
    text = f.read()

order_pattern = re.compile(r'\*\*Order (\d+) \[(SHORT|LONG)\]:\*\*(.*?เวลา:\*\*\s*([\d\-]+ [\d:]+).*?Entry:\*\*\s*([\d\.]+)\s*\|\s*🛑\s*\*\*SL:\*\*\s*([\d\.]+)\s*\|\s*🎯\s*\*\*TP:\*\*\s*([\d\.]+))')
orders = []
for m in order_pattern.finditer(text):
    orders.append({
        'num': int(m.group(1)),
        'type': 'SELL' if m.group(2) == 'SHORT' else 'BUY',
        'time': datetime.datetime.strptime(m.group(4), '%Y-%m-%d %H:%M'),
        'entry': float(m.group(5)),
        'sl': float(m.group(6)),
        'tp': float(m.group(7))
    })

symbol = 'XAUUSD.iux'
spread = 0.15
results = {'WIN': 0, 'LOSE': 0, 'OPEN': 0}

for o in orders:
    rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M1, datetime.datetime.now(), 500000)
    if rates is None or len(rates) == 0:
        print(f"Order {o['num']} -> NO DATA")
        continue
    df = pd.DataFrame(rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    
    mt5_time = o['time'] - datetime.timedelta(hours=1)
    df = df[df['time_dt'] >= mt5_time]
    
    outcome = 'OPEN'
    for row in df.itertuples():
        if o['type'] == 'BUY':
            if row.low <= o['sl']:
                outcome = 'LOSE'
                break
            elif row.high >= o['tp']:
                outcome = 'WIN'
                break
        else: # SELL
            if row.high + spread >= o['sl']:
                outcome = 'LOSE'
                break
            elif row.low + spread <= o['tp']:
                outcome = 'WIN'
                break
    results[outcome] += 1
    print(f"Order {o['num']} {o['type']} (E:{o['entry']} SL:{o['sl']} TP:{o['tp']}) -> {outcome}")

print(results)
mt5.shutdown()
