"""ตรวจ orders session ปัจจุบัน (bot.log) — P/L, ขาดทุน, open"""
import re, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

path = 'logs/bot.log'
orders = {}
seen = set()

def fld(line, key):
    m = re.search(rf'{key}=([^|\s]+)', line)
    return m.group(1) if m else None

for line in open(path, encoding='utf-8', errors='replace'):
    m = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(\S+)', line)
    if not m:
        continue
    ts, kind = m.group(1), m.group(2)
    tk = fld(line, 'ticket')
    if not tk:
        continue

    if kind == 'ORDER_CREATED':
        orders[tk] = {
            'ts': ts, 'side': fld(line, 'signal'), 'tf': fld(line, 'tf'),
            'sid': fld(line, 'sid'), 'entry': fld(line, 'entry'),
            'sl': fld(line, 'sl'), 'tp': fld(line, 'tp'),
            'trend': fld(line, 'trend_filter'),
            'profit': None, 'fate': None, 'close_ts': None,
        }
    elif kind == 'POSITION_CLOSED' and tk in orders and tk not in seen and 'XAUUSD' in line:
        seen.add(tk)
        orders[tk]['profit']   = float(fld(line, 'profit') or 0)
        orders[tk]['close_ts'] = ts
        orders[tk]['fate']     = ('SL' if 'SL Hit' in line else
                                  ('TP' if 'TP Hit' in line else 'Bot'))

closed = {k: v for k, v in orders.items() if v['profit'] is not None}
opn    = {k: v for k, v in orders.items() if v['profit'] is None}
total_pl = sum(v['profit'] for v in closed.values())
wins  = sum(1 for v in closed.values() if v['profit'] > 0)
n     = len(closed)

print("=== Session วันนี้ (07:07 – 12:24 BKK) ===")
print(f"Created: {len(orders)} | Closed: {n} | Open/Pending: {len(opn)}")
print(f"P/L: {total_pl:+.2f} | Win: {wins}/{n} ({100*wins//max(1,n)}%)")
print()

# --- By SID ---
from collections import defaultdict
by_sid = defaultdict(lambda: [0, 0.0, 0])
for v in closed.values():
    sid = v['sid'] or '?'
    by_sid[sid][0] += 1
    by_sid[sid][1] += v['profit']
    if v['profit'] > 0:
        by_sid[sid][2] += 1
print("--- By Strategy ---")
for sid, (cnt, pl, w) in sorted(by_sid.items(), key=lambda x: x[1][1]):
    print(f"  S{sid:2}: {cnt:3} orders | P/L={pl:+7.2f} | Win {w}/{cnt}")
print()

# --- ขาดทุน ---
print("--- Orders ขาดทุน ---")
losing = sorted([v for v in closed.values() if v['profit'] < 0], key=lambda x: x['profit'])
for v in losing:
    trend = v['trend'] or '-'
    print(f"  {v['close_ts']} | {v['side']:4} {v['tf']:4} S{v['sid']:2} | {v['fate']:3} {v['profit']:+7.2f} | entry={v['entry']} trend={trend}")

print()

# --- Bug candidates ---
print("--- Bug candidates (สวนเทรนด์แต่ผ่าน filter / SL Guard ไม่บล็อก) ---")
bugs = []
for v in closed.values():
    if v['profit'] >= 0:
        continue
    trend = v['trend'] or ''
    # สวนเทรนด์: BUY ใน bear หรือ SELL ใน bull
    is_counter = (v['side'] == 'BUY' and 'bear' in trend) or (v['side'] == 'SELL' and 'bull' in trend)
    if is_counter:
        bugs.append(v)
if bugs:
    for v in sorted(bugs, key=lambda x: x['profit']):
        print(f"  {v['close_ts']} | {v['side']:4} {v['tf']:4} S{v['sid']:2} | {v['fate']:3} {v['profit']:+7.2f} | trend={v['trend']}")
else:
    print("  ไม่พบ ✅")
print()

# --- Open/Pending ---
print("--- Open/Pending orders ---")
for tk, v in sorted(opn.items(), key=lambda x: x[1]['ts']):
    print(f"  {v['ts']} | {v['side']:4} {v['tf']:4} S{v['sid']:2} | entry={v['entry']} sl={v['sl']} tp={v['tp']}")
