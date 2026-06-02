"""วิเคราะห์ S15 — order ขาดทุน, หลาย order จุดเดียวกัน, pattern ปัญหา"""
import glob, re, os, sys
from collections import defaultdict, Counter
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

log_dir = 'logs'
def log_files():
    r = []
    for n in ['old_logs/bot-2026-06.log', 'bot.log']:
        p = os.path.join(log_dir, n)
        if os.path.exists(p): r.append(p)
    for p in sorted(glob.glob(os.path.join(log_dir,'old_logs','bot-2026-06.log.bak-*'))):
        if p not in r: r.append(p)
    return r

def fld(line, key):
    m = re.search(rf'{key}=([^|\s]+)', line)
    return m.group(1).strip() if m else None

orders = {}   # ticket -> {created_ts, side, tf, entry, sl, tp, pattern, profit, fate, close_ts}
seen_close = set()

for path in log_files():
    try:
        for line in open(path, encoding='utf-8', errors='replace'):
            m = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(\S+)', line)
            if not m: continue
            ts, kind = m.group(1), m.group(2)
            tk = fld(line, 'ticket')
            if not tk: continue
            sid = fld(line, 'sid')

            if kind == 'ORDER_CREATED' and sid == '15':
                # pattern text between ORDER_CREATED | and | tf=
                pm = re.search(r'ORDER_CREATED \| ([^|]+) \|', line)
                orders[tk] = {
                    'created_ts': ts, 'side': fld(line,'signal'),
                    'tf': fld(line,'tf'), 'entry': fld(line,'entry'),
                    'sl': fld(line,'sl'), 'tp': fld(line,'tp'),
                    'pattern': pm.group(1).strip() if pm else '',
                    'profit': None, 'fate': None, 'close_ts': None,
                    'order_type': fld(line,'order_type'),
                }
            elif kind == 'POSITION_CLOSED' and tk in orders and tk not in seen_close and 'XAUUSD' in line:
                seen_close.add(tk)
                orders[tk]['profit'] = float(fld(line,'profit') or 0)
                orders[tk]['close_ts'] = ts
                orders[tk]['fate'] = ('SL' if 'SL Hit' in line else
                                      ('TP' if 'TP Hit' in line else 'Bot'))
    except: pass

closed = {k:v for k,v in orders.items() if v['profit'] is not None}
print(f"=== S15 Overview ===")
print(f"Created: {len(orders)} | Closed: {len(closed)}")
pl = sum(v['profit'] for v in closed.values())
sl = sum(1 for v in closed.values() if v['fate']=='SL')
tp = sum(1 for v in closed.values() if v['fate']=='TP')
bot = sum(1 for v in closed.values() if v['fate']=='Bot')
wins = sum(1 for v in closed.values() if v['profit']>0)
print(f"P/L: {pl:.2f} | Win: {wins}/{len(closed)} ({100*wins/len(closed):.0f}%) | SL={sl} TP={tp} Bot={bot}")
print()

# By TF
print("=== By TF ===")
tf_grp = defaultdict(lambda: [0,0.0])
for v in closed.values():
    tf_grp[v['tf']][0] += 1
    tf_grp[v['tf']][1] += v['profit']
for tf, (n, p) in sorted(tf_grp.items(), key=lambda x: x[1][1]):
    print(f"  {tf:8}: {n:3} orders | P/L={p:8.2f}")
print()

# By pattern
print("=== By pattern ===")
pat_grp = defaultdict(lambda: [0,0.0])
for v in closed.values():
    key = re.sub(r'[🟢🔴]','',v['pattern']).strip()[:40]
    pat_grp[key][0] += 1
    pat_grp[key][1] += v['profit']
for pat, (n, p) in sorted(pat_grp.items(), key=lambda x: x[1][1]):
    print(f"  {n:3} | P/L={p:8.2f} | {pat}")
print()

# Clustering: multiple orders at same entry/time (the user's concern)
print("=== Clustering: multiple S15 orders ใกล้กัน (entry ±1.0 ใน 3 นาที) ===")
ev = sorted(closed.values(), key=lambda v: v['created_ts'])
clusters = []
used = set()
for i, a in enumerate(ev):
    if id(a) in used or not a['entry']: continue
    grp = [a]
    used.add(id(a))
    for b in ev[i+1:]:
        if id(b) in used or not b['entry']: continue
        try:
            dt_a = a['created_ts']; dt_b = b['created_ts']
            from datetime import datetime
            d = abs((datetime.strptime(dt_b,'%Y-%m-%d %H:%M:%S') -
                     datetime.strptime(dt_a,'%Y-%m-%d %H:%M:%S')).total_seconds())
            if d <= 180 and abs(float(a['entry'])-float(b['entry'])) <= 1.0 and a['side']==b['side']:
                grp.append(b); used.add(id(b))
        except: pass
    if len(grp) >= 2:
        clusters.append(grp)

print(f"พบ {len(clusters)} clusters (≥2 orders จุดเดียวกัน)")
cluster_pl = 0.0; cluster_orders = 0
for grp in sorted(clusters, key=lambda gg: sum(x['profit'] for x in gg))[:15]:
    gp = sum(x['profit'] for x in grp)
    cluster_pl += gp; cluster_orders += len(grp)
    tfs = ",".join(sorted(set(x['tf'] for x in grp)))
    print(f"  {grp[0]['created_ts']} {grp[0]['side']:4} x{len(grp)} entry~{grp[0]['entry']} tf=[{tfs}] | P/L={gp:.2f}")
print(f"\nรวม cluster orders: {sum(len(g) for g in clusters)} | P/L from clusters: {sum(sum(x['profit'] for x in g) for g in clusters):.2f}")
print()

# Loss distribution
print("=== Top 10 losing S15 ===")
for v in sorted(closed.values(), key=lambda v: v['profit'])[:10]:
    print(f"  {v['created_ts']} {v['side']:4} {v['tf']:6} entry={v['entry']} sl={v['sl']} tp={v['tp']} | {v['fate']} {v['profit']:.2f}")
