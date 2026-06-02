#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sim_s1s11_skip_round1.py
จำลอง: ถ้า S1/S11 ข้าม round1 trend recheck ไปทำแค่ round2
เปรียบเทียบ P/L ระหว่าง:
  A = ปิดที่ round1 (ราคาตอนที่ attempt round1 close)
  B = ข้าม round1 → natural close (SL/TP/round2)
"""
import glob, re, os, sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(ROOT, 'logs')

def log_files():
    r = []
    for n in ['old_logs/bot-2026-05.log', 'old_logs/bot-2026-06.log', 'bot.log']:
        p = os.path.join(log_dir, n)
        if os.path.exists(p):
            r.append(p)
    for p in sorted(glob.glob(os.path.join(log_dir, 'old_logs', 'bot-2026-06.log.bak-*'))):
        if p not in r:
            r.append(p)
    return r

def fld(line, key):
    m = re.search(rf'{key}=([^|\s]+)', line)
    return m.group(1).strip() if m else None

# ── Parse ──────────────────────────────────────────────────────────────
round1_attempts = {}   # ticket → {entry, close_at_r1, side, est_pl_r1, ts}
closed_pl       = {}   # ticket → {profit, is_sl, is_tp, is_bot}
sid_map         = {}   # ticket → sid
seen_close      = set()

for path in log_files():
    try:
        for line in open(path, encoding='utf-8', errors='replace'):
            m = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(\S+)', line)
            if not m:
                continue
            ts, kind = m.group(1), m.group(2)
            tk = fld(line, 'ticket')
            if not tk:
                continue

            if kind == 'ORDER_CREATED':
                sid = fld(line, 'sid')
                if sid in ('1', '11'):
                    sid_map[tk] = int(sid)

            elif kind == 'POSITION_CLOSE_REQUEST' and tk in sid_map:
                if 'Fill Trend Recheck [round1' in line and tk not in round1_attempts:
                    bid   = fld(line, 'bid')
                    ask   = fld(line, 'ask')
                    entry = fld(line, 'entry')
                    side  = fld(line, 'side')
                    if bid and entry and side:
                        close_px = float(bid) if side == 'SELL' else float(ask or bid)
                        entry_f  = float(entry)
                        lot      = 0.04
                        if side == 'SELL':
                            est = (entry_f - close_px) * lot * 100
                        else:
                            est = (close_px - entry_f) * lot * 100
                        round1_attempts[tk] = {
                            'ts': ts, 'entry': entry_f,
                            'close_at_r1': close_px,
                            'side': side,
                            'sid': sid_map[tk],
                            'est_pl_r1': round(est, 2),
                        }

            elif kind == 'POSITION_CLOSED' and 'XAUUSD' in line and tk not in seen_close:
                if tk in sid_map:
                    seen_close.add(tk)
                    closed_pl[tk] = {
                        'profit': float(fld(line, 'profit') or 0),
                        'is_sl':  'SL Hit' in line,
                        'is_tp':  'TP Hit' in line,
                        'is_bot': 'Bot' in line,
                    }
    except Exception:
        pass

# ── Match ──────────────────────────────────────────────────────────────
matched = [
    (tk, round1_attempts[tk], closed_pl[tk])
    for tk in round1_attempts
    if tk in closed_pl
]
matched.sort(key=lambda x: x[1]['ts'])

print("=" * 70)
print("  SIM: S1/S11 — Close at Round1  vs  Skip Round1 (natural close)")
print("=" * 70)
print(f"  Orders with round1 attempt + known close: {len(matched)}")
print()

if not matched:
    print("  ไม่มีข้อมูลเพียงพอ")
    sys.exit(0)

pl_r1  = sum(d[1]['est_pl_r1'] for d in matched)
pl_nat = sum(d[2]['profit']    for d in matched)
sl_cnt = sum(1 for d in matched if d[2]['is_sl'])
tp_cnt = sum(1 for d in matched if d[2]['is_tp'])
bot_cnt= sum(1 for d in matched if d[2]['is_bot'])

# S1 vs S11 breakdown
for sid_check in (1, 11):
    sub = [(tk, r1, cl) for tk, r1, cl in matched if r1['sid'] == sid_check]
    if not sub:
        continue
    pA = sum(d[1]['est_pl_r1'] for d in sub)
    pB = sum(d[2]['profit']    for d in sub)
    print(f"  S{sid_check}: {len(sub)} orders  |  R1-close={pA:.2f}  nat-close={pB:.2f}  diff={pA-pB:+.2f}")

print()
print("─" * 70)
print(f"{'':4} {'SCENARIO A':40} {'SCENARIO B':25}")
print(f"{'':4} {'Close at Round 1':40} {'Skip Round1 (natural)':25}")
print("─" * 70)
print(f"  Total P/L         : {pl_r1:>12.2f}           {pl_nat:>12.2f}")
print(f"  Avg per order     : {pl_r1/len(matched):>12.2f}           {pl_nat/len(matched):>12.2f}")
print(f"  SL Hit            : {'N/A':>12}           {sl_cnt:>12}")
print(f"  TP Hit            : {'N/A':>12}           {tp_cnt:>12}")
print(f"  Bot close         : {'N/A':>12}           {bot_cnt:>12}")
print()

diff = pl_r1 - pl_nat
verdict = "BETTER" if diff > 0 else "WORSE"
print("=" * 70)
print(f"  DIFF (A - B): {diff:+.2f} USD")
print(f"  Close at Round1 is {verdict} by {abs(diff):.2f} USD across {len(matched)} orders")
print("=" * 70)
print()

# Detailed breakdown
r1_better = [(d[1]['est_pl_r1'], d[2]['profit']) for d in matched if d[1]['est_pl_r1'] > d[2]['profit']]
r1_worse  = [(d[1]['est_pl_r1'], d[2]['profit']) for d in matched if d[1]['est_pl_r1'] <= d[2]['profit']]
print(f"  R1 close BETTER than natural: {len(r1_better):3} orders | P/L saved: {sum(r1-nat for r1,nat in r1_better):+.2f}")
print(f"  R1 close WORSE  than natural: {len(r1_worse):3} orders | P/L cost : {sum(r1-nat for r1,nat in r1_worse):+.2f}")
print()

# Distribution of R1 estimated P/L
import statistics
r1_pls = [d[1]['est_pl_r1'] for d in matched]
nat_pls = [d[2]['profit']   for d in matched]
print(f"  R1 close distribution:")
print(f"    median={statistics.median(r1_pls):.2f}  min={min(r1_pls):.2f}  max={max(r1_pls):.2f}")
print(f"  Natural close distribution:")
print(f"    median={statistics.median(nat_pls):.2f}  min={min(nat_pls):.2f}  max={max(nat_pls):.2f}")
print()

# Top cases where skip would HELP
print("  Top 10 cases where SKIP Round1 would HELP (save most):")
helps = sorted(matched, key=lambda x: x[2]['profit'] - x[1]['est_pl_r1'], reverse=True)[:10]
print(f"  {'ticket':12} {'S':3} {'tf':12} {'R1_est':8} {'natural':8} {'saved':8} fate")
for tk, r1, cl in helps:
    fate = 'SL' if cl['is_sl'] else ('TP' if cl['is_tp'] else 'Bot')
    saved = cl['profit'] - r1['est_pl_r1']
    print(f"  {tk:12} S{r1['sid']:<2} {r1['side']:5} {r1['est_pl_r1']:8.2f} {cl['profit']:8.2f} {saved:+8.2f} {fate}")
