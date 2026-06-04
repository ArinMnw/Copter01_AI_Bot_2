"""check_bugs_today.py — หา bug/notable orders วันนี้"""
import re, sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

log = open('logs/bot.log', encoding='utf-8', errors='replace').readlines()
fills = {}; closes = {}; seen = set()

def fld(line, key):
    m = re.search(rf'{key}=([^|\s]+)', line)
    return m.group(1) if m else ''

for line in log:
    m = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(\S+)', line)
    if not m: continue
    ts, kind = m.group(1), m.group(2)
    tk = fld(line, 'ticket')
    if not tk: continue
    if kind == 'ENTRY_FILL' and tk not in fills:
        fills[tk] = {'fill_ts': ts, 'side': fld(line,'side'), 'tf': fld(line,'tf'),
                     'sid': fld(line,'sid'), 'price': fld(line,'price'),
                     'trend': fld(line,'trend')}
    elif kind == 'POSITION_CLOSED' and tk not in seen and 'XAUUSD' in line:
        seen.add(tk)
        closes[tk] = {'profit': fld(line,'profit'), 'reason': fld(line,'reason'), 'close_ts': ts}

bugs = []
for tk, cl in closes.items():
    fi = fills.get(tk, {})
    profit = float(cl.get('profit','0') or 0)
    reason = cl.get('reason','')
    side = fi.get('side','')
    trend = fi.get('trend','').lower()
    is_counter = (side=='BUY' and 'bear' in trend) or (side=='SELL' and 'bull' in trend)
    if abs(profit) > 5 or (profit < 0 and is_counter):
        bugs.append({'ticket': tk, 'fill_ts': fi.get('fill_ts',''), 'sid': fi.get('sid',''),
                     'side': side, 'tf': fi.get('tf',''), 'trend': fi.get('trend',''),
                     'profit': profit, 'reason': reason, 'is_counter': is_counter})

bugs.sort(key=lambda x: x['profit'])
print(f'Bug/notable orders: {len(bugs)}')
print(f"{'Fill':20} {'S':3} {'Side':4} {'TF':5} {'Trend':15} {'Profit':8}  {'Reason':22} Flag")
print("-"*90)
for b in bugs[:25]:
    flag = 'COUNTER' if b['is_counter'] else ''
    sid = b['sid']
    fill = b['fill_ts']
    side = b['side']
    tf = b['tf']
    trend = b['trend']
    profit = b['profit']
    reason = b['reason']
    print(f"{fill:20} S{sid:<2} {side:4} {tf:5} {trend:15} {profit:+7.2f}   {reason[:22]:22} {flag}")
