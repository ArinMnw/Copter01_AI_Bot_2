# -*- coding: utf-8 -*-
"""สคริปต์ sweep ชั่วคราว: จูน tp_r ต่อ sid ผ่าน dual-window (H1/H2 ของ 365 วันล่าสุด)
เกณฑ์ผ่าน: net profit เป็นบวกทั้งสองหน้าต่าง (กัน overfit ตามเช็คลิสต์ข้อ 14/15)
ไม่แก้ default ใดๆ ในโค้ดหลัก ใช้ env var S20_TUNE_PARAMS ที่เพิ่มไว้เป็น opt-in hook เท่านั้น
"""
import os, re, subprocess, json, sys

STRATS = ["S20_18", "S20_19", "S20_20", "S20_21", "S20_22", "S20_24", "S20_28",
          "S20_301", "S20_302", "S20_303", "S20_304"]
SID_MAP = {"S20_18": 20.18, "S20_19": 20.19, "S20_20": 20.20, "S20_21": 20.21,
           "S20_22": 20.22, "S20_24": 20.24, "S20_28": 20.28,
           "S20_301": 20.301, "S20_302": 20.302, "S20_303": 20.303, "S20_304": 20.304}
CANDIDATES = [1.0, 1.5, 1.8, 2.5, 4.0]
WINDOWS = [("2025-09-22", "2026-03-22"), ("2026-03-22", "2026-09-22")]

def run(strat, tp_r, start, end):
    sid = SID_MAP[strat]
    env = os.environ.copy()
    env["S20_TUNE_PARAMS"] = json.dumps({str(sid): {"tp_r": tp_r}})
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, "strategy/backtest_s20_unified.py", "--strategy", strat,
           "--start", start, "--end", end, "--balance", "5000"]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=env, cwd=os.path.dirname(__file__) or ".").stdout
    m = re.search(r"Net Profit:\s+\$([-\d,\.]+)", out)
    t = re.search(r"Total Trades Executed:\s+([\d,]+)", out)
    wr = re.search(r"Overall Win Rate:\s+([\d\.]+)%", out)
    if not m:
        return None
    return float(m.group(1).replace(",", "")), int(t.group(1).replace(",", "")) if t else 0, float(wr.group(1)) if wr else 0.0

results = {}
for strat in STRATS:
    row = {}
    for tp_r in CANDIDATES:
        vals = [run(strat, tp_r, s, e) for s, e in WINDOWS]
        row[tp_r] = vals
        h1, h2 = vals
        h1s = f"{h1[0]:+.0f}(n{h1[1]},{h1[2]:.0f}%)" if h1 else "ERR"
        h2s = f"{h2[0]:+.0f}(n{h2[1]},{h2[2]:.0f}%)" if h2 else "ERR"
        print(f"{strat} tp_r={tp_r:.1f}  H1={h1s}  H2={h2s}", flush=True)
    results[strat] = row

print("\n=== SUMMARY (best dual-positive) ===")
for strat, row in results.items():
    best = None
    for tp_r, vals in row.items():
        h1, h2 = vals
        if h1 and h2 and h1[0] > 0 and h2[0] > 0:
            tot = h1[0] + h2[0]
            if best is None or tot > best[1]:
                best = (tp_r, tot, h1[0], h2[0])
    if best:
        print(f"{strat}: tp_r={best[0]:.1f} PASS dual-window  H1={best[2]:+.0f} H2={best[3]:+.0f} total={best[1]:+.0f}")
    else:
        print(f"{strat}: NO dual-window-positive tp_r in {CANDIDATES}")
