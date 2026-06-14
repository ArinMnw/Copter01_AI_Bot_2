"""ตรวจ S15 orders วันนี้ — แยก code เก่า/ใหม่"""
import glob, re, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

log_dir = 'logs'
DATE_FROM   = '2026-06-03 06:00'
CUTOFF_NEW  = '2026-06-03 09:00'   # user deploys new code at 09:00

def log_files():
    from log_sources import bot_log_files
    return bot_log_files()

def fld(line, key):
    m = re.search(rf'{key}=([^|\s]+)', line)
    return m.group(1).strip() if m else None

orders = {}
seen_close = set()

for path in log_files():
    try:
        for line in open(path, encoding='utf-8', errors='replace'):
            m = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(\S+)', line)
            if not m:
                continue
            ts, kind = m.group(1), m.group(2)
            if ts < DATE_FROM:
                continue
            tk = fld(line, 'ticket')
            if not tk:
                continue

            if kind == 'ORDER_CREATED' and fld(line, 'sid') == '15':
                pm = re.search(r'ORDER_CREATED \| ([^|]+) \|', line)
                orders[tk] = {
                    'ts': ts, 'side': fld(line, 'signal'), 'tf': fld(line, 'tf'),
                    'entry': fld(line, 'entry'), 'sl': fld(line, 'sl'), 'tp': fld(line, 'tp'),
                    'pattern': pm.group(1).strip() if pm else '',
                    'profit': None, 'fate': None,
                    'new_code': ts >= CUTOFF_NEW,
                }
            elif kind == 'POSITION_CLOSED' and tk in orders and tk not in seen_close and 'XAUUSD' in line:
                seen_close.add(tk)
                orders[tk]['profit'] = float(fld(line, 'profit') or 0)
                orders[tk]['fate'] = ('SL' if 'SL Hit' in line else
                                      ('TP' if 'TP Hit' in line else 'Bot'))
    except:
        pass

old_orders = [v for v in orders.values() if not v['new_code']]
new_orders = [v for v in orders.values() if v['new_code']]
old_closed = [v for v in old_orders if v['profit'] is not None]
new_closed = [v for v in new_orders if v['profit'] is not None]

print(f"=== S15 วันนี้ (ข้อมูล {DATE_FROM} — 12:24 BKK) ===")
print()
print(f"CODE เก่า (ก่อน 09:00): {len(old_orders)} orders, ปิดแล้ว {len(old_closed)}")
if old_closed:
    op = sum(v['profit'] for v in old_closed)
    ow = sum(1 for v in old_closed if v['profit'] > 0)
    print(f"  P/L={op:+.2f} | Win {ow}/{len(old_closed)} ({100*ow//max(1,len(old_closed))}%)")
print()
print(f"CODE ใหม่ (09:00+):      {len(new_orders)} orders")
if new_orders:
    print(f"  ปิดแล้ว {len(new_closed)}")
else:
    print(f"  (ไม่มี order — filter บล็อกทั้งหมด หรือ market ไม่มี signal)")
print()

print(f"{'ts':20} {'tag':3} {'side':4} {'tf':4} {'entry':8} {'fate':4} {'P/L':8}  pattern")
print("-"*90)
for tk, v in sorted(orders.items(), key=lambda x: x[1]['ts']):
    tag  = 'NEW' if v['new_code'] else 'old'
    pl   = f"{v['profit']:+.2f}" if v['profit'] is not None else 'open '
    fate = v['fate'] or '-'
    pat  = re.sub(r'[^\x00-\x7F]', '', v['pattern'])[:30]
    print(f"  {v['ts']:20} {tag:3} {v['side'] or '?':4} {v['tf'] or '?':4} {v['entry'] or '?':8} {fate:4} {pl:8}  {pat}")
