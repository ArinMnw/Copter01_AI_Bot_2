"""ตรวจ S15 orders หลัง restart ล่าสุด + summary รายวัน"""
import glob, re, os, sys
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

log_dir = 'logs'
CUTOFF = '2026-06-03 12:25'  # latest restart with new strict code

def log_files():
    r = []
    for n in ['old_logs/bot-2026-06.log', 'bot.log']:
        p = os.path.join(log_dir, n)
        if os.path.exists(p): r.append(p)
    for p in sorted(glob.glob(os.path.join(log_dir, 'old_logs', 'bot-2026-06.log.bak-*'))):
        if p not in r: r.append(p)
    return r

def fld(line, key):
    m = re.search(rf'{key}=([^|\s]+)', line)
    return m.group(1).strip() if m else None

orders = {}
seen_close = set()

for path in log_files():
    try:
        for line in open(path, encoding='utf-8', errors='replace'):
            m = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(\S+)', line)
            if not m: continue
            ts, kind = m.group(1), m.group(2)
            tk = fld(line, 'ticket')
            if not tk: continue

            if kind == 'ORDER_CREATED' and fld(line, 'sid') == '15':
                pm = re.search(r'ORDER_CREATED \| ([^|]+) \|', line)
                orders[tk] = {
                    'created_ts': ts, 'side': fld(line, 'signal'),
                    'tf': fld(line, 'tf'), 'entry': fld(line, 'entry'),
                    'pattern': pm.group(1).strip() if pm else '',
                    'profit': None, 'fate': None, 'is_new': ts >= CUTOFF
                }
            elif kind == 'POSITION_CLOSED' and tk in orders and tk not in seen_close and 'XAUUSD' in line:
                seen_close.add(tk)
                orders[tk]['profit'] = float(fld(line, 'profit') or 0)
                orders[tk]['fate'] = ('SL' if 'SL Hit' in line else ('TP' if 'TP Hit' in line else 'Bot'))
    except:
        pass

# แยก old vs new
old_closed = {k: v for k, v in orders.items() if not v['is_new'] and v['profit'] is not None}
new_created = {k: v for k, v in orders.items() if v['is_new']}
new_closed  = {k: v for k, v in new_created.items() if v['profit'] is not None}

print(f"=== S15: ก่อน/หลัง restart {CUTOFF} ===")
print(f"  ก่อน: created={sum(1 for v in orders.values() if not v['is_new'])} | closed={len(old_closed)}")
if old_closed:
    op = sum(v['profit'] for v in old_closed.values())
    ow = sum(1 for v in old_closed.values() if v['profit'] > 0)
    print(f"  ก่อน P/L: {op:.2f} | win {ow}/{len(old_closed)} ({100*ow/len(old_closed):.0f}%)")

print(f"\n  หลัง (new code): created={len(new_created)} | closed={len(new_closed)}")
if new_closed:
    np_ = sum(v['profit'] for v in new_closed.values())
    nw  = sum(1 for v in new_closed.values() if v['profit'] > 0)
    print(f"  หลัง P/L: {np_:.2f} | win {nw}/{len(new_closed)} ({100*nw/max(1,len(new_closed)):.0f}%)")

print(f"\n=== S15 orders (หลัง {CUTOFF}) ===")
print(f"{'ts':20} {'side':4} {'tf':4} {'entry':8} {'fate':4} {'P/L':8} pattern")
for tk, v in sorted(new_created.items(), key=lambda x: x[1]['created_ts']):
    pat = re.sub(r'[^\x00-\x7F]', '', v['pattern'])[:35]
    pl_str = f"{v['profit']:+.2f}" if v['profit'] is not None else 'open'
    fate   = v['fate'] or '-'
    print(f"  {v['created_ts']:20} {v['side'] or '?':4} {v['tf'] or '?':4} {v['entry'] or '?':8} {fate:4} {pl_str:8} {pat}")

# Check for duplicates in new orders
print(f"\n=== Cluster check (new orders, entry ±0.5 ใน 5min) ===")
from datetime import datetime
evlist = sorted(new_created.values(), key=lambda x: x['created_ts'])
used = set()
found = 0
for i, a in enumerate(evlist):
    if id(a) in used or not a['entry']: continue
    grp = [a]
    used.add(id(a))
    for b in evlist[i+1:]:
        if id(b) in used or not b['entry']: continue
        try:
            dt = abs((datetime.strptime(b['created_ts'], '%Y-%m-%d %H:%M:%S') -
                      datetime.strptime(a['created_ts'], '%Y-%m-%d %H:%M:%S')).total_seconds())
            if dt <= 300 and abs(float(a['entry']) - float(b['entry'])) <= 0.5 and a['side'] == b['side']:
                grp.append(b); used.add(id(b))
        except:
            pass
    if len(grp) >= 2:
        found += 1
        tfs = ','.join(sorted(set(x['tf'] for x in grp if x['tf'])))
        gp  = sum(x['profit'] for x in grp if x['profit'] is not None)
        print(f"  {grp[0]['created_ts']} {grp[0]['side']} x{len(grp)} entry~{grp[0]['entry']} tf=[{tfs}] P/L={gp:.2f}")

if found == 0:
    print("  ไม่พบ cluster ซ้ำ ✅")
