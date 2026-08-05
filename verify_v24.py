import pandas as pd
import datetime
import re

# Load manual trades
with open('docs/allin4s/Full Trading/full_trading.md', 'r', encoding='utf-8') as f:
    text = f.read()

order_pattern = re.compile(r'\*\*Order (\d+) \[(SHORT|LONG)\]:\*\*(.*?เวลา:\*\*\s*([\d\-]+ [\d:]+))')
manual_orders = []
for m in order_pattern.finditer(text):
    manual_orders.append({
        'num': int(m.group(1)),
        'type': 'SELL' if m.group(2) == 'SHORT' else 'BUY',
        'time': datetime.datetime.strptime(m.group(4), '%Y-%m-%d %H:%M'),
    })

# Load simulated trades
try:
    df_sim = pd.read_csv('strategy/s20.14.1/excel/trades.csv')
    df_sim['Time (BKK)'] = pd.to_datetime(df_sim['Time (BKK)'])
except FileNotFoundError:
    print("Error: excel/trades.csv not found")
    exit()

matched = 0
for o in manual_orders:
    # Look for simulated trade within +/- 12 hours (due to timeframe differences and structure setup times)
    start_time = o['time'] - datetime.timedelta(hours=12)
    end_time = o['time'] + datetime.timedelta(hours=12)
    
    matches = df_sim[(df_sim['Type'] == o['type']) & 
                     (df_sim['Time (BKK)'] >= start_time) & 
                     (df_sim['Time (BKK)'] <= end_time)]
                     
    if not matches.empty:
        matched += 1
        best = matches.iloc[0]
        outcome = best['Reason'] if 'Reason' in best else 'UNKNOWN'
        print(f"MATCH Order {o['num']:02d} | {o['time'].strftime('%Y-%m-%d %H:%M')} | {o['type']:>4} -> MATCHED {len(matches)} trades (Pattern: {best['Pattern']}, Outcome: {outcome})")
    else:
        print(f"MISS  Order {o['num']:02d} | {o['time'].strftime('%Y-%m-%d %H:%M')} | {o['type']:>4} -> NOT FOUND")

print(f"\nSummary: {matched}/{len(manual_orders)} manual trades found in v24 simulation.")
