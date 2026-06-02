#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""อ่าน orders_old_vs_new.csv -> แสดง order ที่ผลต่าง (abnormal) เรียงตามเวลา ตั้งแต่ 5/26
   group ตามวัน + subtotal รายวัน"""
import os, csv, io, sys
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(ROOT, "orders_old_vs_new.csv")

rows = []
with open(CSV, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        rows.append(r)

# เฉพาะ order ที่ผลต่าง (abnormal)
aff = [r for r in rows if r["status"] != "SAME"]
aff.sort(key=lambda r: r["create_ts"])

day_sub = defaultdict(lambda: [0, 0.0, 0.0])  # n, old, new
for r in aff:
    d = day_sub[r["create_ts"][:10]]
    d[0] += 1; d[1] += float(r["OLD_profit"]); d[2] += float(r["NEW_profit"])

print("=" * 104)
print(f"  Order ผิดปกติ (guard ใหม่กระทบ) เรียงตามเวลา ตั้งแต่ 2026-05-26  [{len(aff)} ตัว จาก 808 SL]")
print("=" * 104)
print(f"  {'create':<17}{'ticket':>11} {'sd':>4} {'tf':>4}{'sid':>4} {'OLD':>8} {'NEW':>8} {'diff':>8}  {'status':<11} trend")
cur_day = None
for r in aff:
    d = r["create_ts"][:10]
    if d != cur_day:
        cur_day = d
        n, o, nw = day_sub[d]
        print(f"  ── {d} ──  ({n} ตัว | OLD {o:.2f} -> NEW {nw:.2f} | ดีขึ้น {nw-o:+.2f})")
    diff = float(r["diff"])
    print(f"  {r['create_ts']:<17}{r['ticket']:>11} {r['side']:>4} {r['tf']:>4}{str(r['sid']):>4} "
          f"{float(r['OLD_profit']):>8.2f} {float(r['NEW_profit']):>8.2f} {diff:>8.2f}  {r['status']:<11} {r['trend_filter']}")

print()
print("=" * 70)
print("  สรุปรายวัน (เฉพาะ order ที่ผลต่าง)")
print("=" * 70)
print(f"  {'day':<12}{'n':>5}{'OLD':>11}{'NEW':>11}{'ดีขึ้น':>11}")
to, tn = 0.0, 0.0
for d in sorted(day_sub):
    n, o, nw = day_sub[d]
    to += o; tn += nw
    print(f"  {d:<12}{n:>5}{o:>11.2f}{nw:>11.2f}{nw-o:>11.2f}")
print("-" * 50)
print(f"  {'รวม':<12}{len(aff):>5}{to:>11.2f}{tn:>11.2f}{tn-to:>11.2f}")
