import os
import pandas as pd
import re
from datetime import datetime, timedelta

md_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docs', 'allin4s', 'Full Trading', 'full_trading.md'))
with open(md_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Parse orders
# e.g.: 23. **Order 23 [LONG]:** `"Qml 12H"` — 🕒 **เวลา:** 2026-07-17 14:00 | 💰 **Entry:** 3959.72 | 🛑 **SL:** 3941.94 | 🎯 **TP:** 3988.49
order_pattern = re.compile(r'\*\*Order (\d+) \[(SHORT|LONG)\]:\*\*(.*?เวลา:\*\*\s*([\d\-]+ [\d:]+).*?Entry:\*\*\s*([\d\.]+)\s*\|\s*🛑\s*\*\*SL:\*\*\s*([\d\.]+)\s*\|\s*🎯\s*\*\*TP:\*\*\s*([\d\.]+))')
orders = []
for m in order_pattern.finditer(content):
    num = int(m.group(1))
    side = 'SELL' if m.group(2) == 'SHORT' else 'BUY'
    full_str = m.group(3)
    dt_str = m.group(4)
    price = float(m.group(5))
    sl = float(m.group(6))
    tp = float(m.group(7))
    dt_mt5 = datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
    dt_bkk = dt_mt5 + timedelta(hours=1)
    orders.append({
        'num': num,
        'type': side,
        'time_bkk': dt_bkk,
        'entry': price,
        'sl': sl,
        'tp': tp,
        'matched_all': False,
        'matched_time_only': False,
        'match_info': ''
    })

csv_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'excel'))
csv_files = ['trades.csv']
all_trades = []
for f in csv_files:
    filepath = os.path.join(csv_dir, f)
    if not os.path.exists(filepath): continue
    df = pd.read_csv(filepath)
    for _, row in df.iterrows():
        all_trades.append({
            'time_bkk': datetime.strptime(row['Time (BKK)'], '%Y-%m-%d %H:%M'),
            'type': row['Type'],
            'entry': float(row['Entry']),
            'sl': float(row['SL']),
            'tp': float(row['TP']),
            'pattern': row['Pattern'],
            'TF': row['TF'],
            'rsi': float(row['RSI']),
            'atr': float(row['ATR']),
            'reason': row.get('Reason', 'Unknown'),
            'file': f
        })

for o in orders:
    matches = []
    for t in all_trades:
        # Check time within 12 hours AND exact type
        if t['type'] == o['type'] and abs((t['time_bkk'] - o['time_bkk']).total_seconds()) <= 12 * 3600:
            # Check price, SL, TP within 3.0 margin
            entry_match = abs(t['entry'] - o['entry']) <= 5.0
            sl_match = abs(t['sl'] - o['sl']) <= 5.0
            tp_match = abs(t['tp'] - o['tp']) <= 5.0
            
            if entry_match and sl_match and tp_match:
                matches.append((t, True))
            else:
                matches.append((t, False))
                
    if matches:
        exact_matches = [m for m in matches if m[1]]
        if exact_matches:
            o['matched_all'] = True
            m_t = exact_matches[0][0]
            o['match_info'] = f"EXACT MATCH in {m_t['file']} (Bot TF:{m_t['TF']} Result:{m_t['reason']} E:{m_t['entry']} SL:{m_t['sl']} TP:{m_t['tp']} pat:{m_t['pattern']} RSI:{m_t['rsi']})"
            o['match_reason'] = m_t['reason']
        else:
            o['matched_time_only'] = True
            m_t = matches[0][0]
            o['match_info'] = f"TIME MATCH ONLY in {m_t['file']} (Bot TF:{m_t['TF']} Result:{m_t['reason']} E:{m_t['entry']} SL:{m_t['sl']} TP:{m_t['tp']} pat:{m_t['pattern']} RSI:{m_t['rsi']})"
            o['match_reason'] = m_t['reason']

exact_count = sum(1 for o in orders if o['matched_all'])
time_count = sum(1 for o in orders if o['matched_time_only'])

tp_count = sum(1 for o in orders if o.get('match_reason') == 'TP')
be_count = sum(1 for o in orders if o.get('match_reason') == 'BE')
sl_count = sum(1 for o in orders if o.get('match_reason') == 'SL')
open_count = sum(1 for o in orders if o.get('match_reason') == 'OPEN')

print(f"Total Exact Matches (Entry, SL, TP): {exact_count} / {len(orders)}")
print(f"Total Time+Type Matches Only: {time_count} / {len(orders)}")
print(f"Outcome of the matched orders => WIN (TP): {tp_count} | BE: {be_count} | LOSE (SL): {sl_count} | OPEN: {open_count}")

for o in orders:
    if o.get('matched_all') or o.get('matched_time_only'):
        print(f"Order {o['num']} [{o['type']}] {o['time_bkk'].strftime('%Y-%m-%d %H:%M')} E:{o['entry']} | {o['match_info']}")
