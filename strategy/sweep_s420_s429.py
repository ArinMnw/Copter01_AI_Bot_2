# -*- coding: utf-8 -*-
"""ไล่ backtest S420-S429 ทุกกลยุทธ์ x ทุก TF (M1/M5/M15/M30/H1) x หน้าต่าง
เวลาหลายขนาด (30/60/90/120/150/180/270/365 วันย้อนหลังจากตอนนี้) เพื่อหาว่า
TF ไหนของกลยุทธ์ไหน "กำไรตลอด" (net_profit>0 ทุกหน้าต่างที่มีข้อมูลพอ)

ใช้ default cfg ของแต่ละกลยุทธ์ (ไม่ tune) fixed lot (balance=100 -> lot=0.01)
spread=0.20 — ข้าม (N/A) ถ้าประวัติราคาไม่พอสำหรับหน้าต่างนั้น (เช่น M1 ที่มี
ประวัติแค่ ~205 วัน จะข้าม 270/365)

Usage: python sweep_s420_s429.py > sweep_result.txt
"""

from __future__ import annotations

import importlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone

BKK = timezone(timedelta(hours=7))
STRATS = [f"s{n}" for n in range(420, 430)]
WINDOWS_DAYS = [30, 60, 90, 120, 150, 180, 270, 365]
TF_LIST = ["M1", "M5", "M15", "M30", "H1"]
SPREAD = 0.20
BALANCE = 100.0
LOT = BALANCE / 10000.0

end_bkk = datetime.now(BKK)

results = {}  # results[strategy][tf][days] = net_profit or None

t0 = time.time()
for strat in STRATS:
    mod = importlib.import_module(f"{strat}.backtest_{strat}")
    results[strat] = {tf: {} for tf in TF_LIST}
    for tf in TF_LIST:
        if tf not in mod.TF_MAP:
            for d in WINDOWS_DAYS:
                results[strat][tf][d] = None
            continue
        for d in WINDOWS_DAYS:
            start_bkk = end_bkk - timedelta(days=d)
            try:
                summary, _trades = mod.backtest(tf, SPREAD, LOT, start_bkk, end_bkk)
                results[strat][tf][d] = summary.get("net_profit")
            except RuntimeError as exc:
                results[strat][tf][d] = None
            except Exception as exc:  # noqa: BLE001 - ไม่อยากให้ 1 error ล้มทั้ง sweep
                print(f"[ERROR] {strat} {tf} {d}d: {exc}", file=sys.stderr, flush=True)
                results[strat][tf][d] = None
            elapsed = time.time() - t0
            print(f"[{elapsed:7.1f}s] {strat} {tf} {d}d -> "
                  f"{results[strat][tf][d]}", flush=True)

print("\n\n===== JSON RESULT =====")
print(json.dumps(results, indent=2))

print("\n\n===== TF ที่กำไรตลอด (ทุกหน้าต่างที่มีข้อมูล) ต่อกลยุทธ์ =====")
for strat in STRATS:
    good_tfs = []
    for tf in TF_LIST:
        values = [v for v in results[strat][tf].values() if v is not None]
        if not values:
            continue
        if all(v > 0.0 for v in values):
            good_tfs.append((tf, len(values), min(values), max(values)))
    if good_tfs:
        parts = ", ".join(f"{tf}(n={n},min={mn:.2f},max={mx:.2f})" for tf, n, mn, mx in good_tfs)
        print(f"{strat.upper()}: {parts}")
    else:
        print(f"{strat.upper()}: (ไม่มี TF ไหนกำไรตลอด)")
