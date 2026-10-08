# -*- coding: utf-8 -*-
"""sweep entry params (sl_mult, active_depth) ของ SMC family (301-304 ใช้ entry logic ร่วมกัน)
ใช้ S20_304 เป็นตัวแทน (ทุก sid ได้ entry เดียวกัน) tp_r fix ที่ 1.8 ระหว่าง sweep นี้"""
import os, re, subprocess, json, sys

WINDOWS = [("2025-09-22", "2026-03-22"), ("2026-03-22", "2026-09-22")]
SL_MULT = [0.20, 0.30, 0.50]
ACTIVE_DEPTH = [0.20, 0.35, 0.60]

def run(sl_mult, active_depth, start, end):
    env = os.environ.copy()
    env["S20_ENTRY_TUNE_PARAMS"] = json.dumps({"sl_mult": sl_mult, "active_depth": active_depth})
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, "strategy/backtest_s20_unified.py", "--strategy", "S20_304",
           "--start", start, "--end", end, "--balance", "5000"]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=env, cwd=os.path.dirname(__file__) or ".").stdout
    m = re.search(r"Net Profit:\s+\$([-\d,\.]+)", out)
    t = re.search(r"Total Trades Executed:\s+([\d,]+)", out)
    wr = re.search(r"Overall Win Rate:\s+([\d\.]+)%", out)
    if not m:
        print("ERROR OUTPUT TAIL:", out[-500:])
        return None
    return float(m.group(1).replace(",", "")), int(t.group(1).replace(",", "")) if t else 0, float(wr.group(1)) if wr else 0.0

best = None
for sl in SL_MULT:
    for ad in ACTIVE_DEPTH:
        vals = [run(sl, ad, s, e) for s, e in WINDOWS]
        h1, h2 = vals
        h1s = f"{h1[0]:+.0f}(n{h1[1]},{h1[2]:.0f}%)" if h1 else "ERR"
        h2s = f"{h2[0]:+.0f}(n{h2[1]},{h2[2]:.0f}%)" if h2 else "ERR"
        print(f"sl_mult={sl:.2f} active_depth={ad:.2f}  H1={h1s}  H2={h2s}", flush=True)
        if h1 and h2:
            tot = h1[0] + h2[0]
            dual_pos = h1[0] > 0 and h2[0] > 0
            if best is None or (dual_pos, tot) > (best[0], best[1]):
                best = (dual_pos, tot, sl, ad, h1[0], h2[0])

print("\n=== BEST ===")
if best:
    print(f"sl_mult={best[2]} active_depth={best[3]} dual_positive={best[0]} total={best[1]:+.0f} H1={best[4]:+.0f} H2={best[5]:+.0f}")
