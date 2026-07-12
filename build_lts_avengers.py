"""ประกอบร่าง LTS Avengers: แปลง ladder log -> weights file + สรุปสถิติ portfolio

1. อ่าน lts_auto_ladder_log.md, dedup ต่อ AF index (เก็บบรรทัดล่าสุด — สาย chain ที่รอด
   หลัง crash/resume), ตัดที่ --max-idx
2. รวมน้ำหนักต่อ label (blend เป็นเชิงเส้น: leg เดิมซ้ำหลายขั้น = บวกน้ำหนักได้เลย)
3. เขียน strategy/lts/optimized_weights/lts_avengers_weights.txt (ฟอร์แมตเดียวกับ
   lts_optimized_weights.txt — โหลดผ่าน strategy_lts._load_lts_weights ได้ทันที)
4. อ่าน daily csv ตัวสุดท้าย -> P&L รวม, avg/day, %วันบวก, MaxDD ของ equity curve
"""
import argparse
import os
import re
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--log", default="lts_auto_ladder_log.md")
ap.add_argument("--max-idx", type=int, default=2000)
ap.add_argument("--daily", required=True, help="daily csv ของขั้นสุดท้าย")
ap.add_argument("--out", default=os.path.join("strategy", "lts", "optimized_weights",
                                              "lts_avengers_weights.txt"))
args = ap.parse_args()

pat = re.compile(r"^- AF(\d+) = AF\d+ \+ (\S+?)x([0-9.]+) -> avg: ([0-9.\-]+), min: ([0-9.\-]+)")
chain = {}
with open(args.log, encoding="utf-8") as f:
    for line in f:
        m = pat.match(line.strip())
        if not m:
            continue
        idx = int(m.group(1))
        if idx <= args.max_idx:
            chain[idx] = (m.group(2), float(m.group(3)), float(m.group(4)), float(m.group(5)))

if not chain:
    print("no chain lines parsed")
    sys.exit(1)

max_idx = max(chain)
print(f"chain: AF1..AF{max_idx} ({len(chain)} steps)")
final_avg, final_min = chain[max_idx][2], chain[max_idx][3]

# aggregate weights per label
weights = {}
order = []
for idx in sorted(chain):
    label, w, _, _ = chain[idx]
    if label not in weights:
        weights[label] = 0.0
        order.append(label)
    weights[label] += w

os.makedirs(os.path.dirname(args.out), exist_ok=True)
with open(args.out, "w", encoding="utf-8") as f:
    for label in order:
        f.write(f"{label} : {weights[label]:.3f}\n")
print(f"wrote {args.out} ({len(order)} unique legs from {len(chain)} ladder steps)")

# portfolio stats from daily csv
import csv as _csv
days = []
with open(args.daily, encoding="utf-8") as f:
    for row in _csv.DictReader(f):
        days.append(float(row["total"]))
n = len(days)
total = sum(days)
pos = sum(1 for d in days if d > 0)
neg = sum(1 for d in days if d < 0)
cum = 0.0
peak = 0.0
maxdd = 0.0
for d in days:
    cum += d
    peak = max(peak, cum)
    maxdd = max(maxdd, peak - cum)
worst = min(days)
best = max(days)
print(f"--- Portfolio (window {n} days) ---")
print(f"ladder avg/day (log): {final_avg:.2f} | min window avg: {final_min:.2f}")
print(f"total P&L: {total:,.2f} | avg/day: {total/n:,.2f}")
print(f"day win rate: {pos}/{pos+neg} = {pos/(pos+neg)*100:.1f}% | best day {best:,.2f} | worst day {worst:,.2f}")
print(f"Max Drawdown (equity curve): {maxdd:,.2f} ({maxdd/max(total,1e-9)*100:.2f}% of total)")
