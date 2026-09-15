# -*- coding: utf-8 -*-
"""ไล่ backtest S420/S421 ใหม่หลังแก้บั๊ก look-ahead (exit-check เคยอ้าง
fib_tp/fib_sl ที่คำนวณใหม่ทุกแท่งจาก pattern ล่าสุด แทนที่จะใช้
position["tp"]/position["sl"] ที่ล็อกไว้ตอนเปิดไม้) x ทุก TF x 8 หน้าต่างเวลา
เหมือน sweep_s420_s429.py เดิม แต่รันแค่ 2 กลยุทธ์นี้"""

from __future__ import annotations

import importlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone

BKK = timezone(timedelta(hours=7))
STRATS = ["s420", "s421"]
WINDOWS_DAYS = [30, 60, 90, 120, 150, 180, 270, 365]
TF_LIST = ["M1", "M5", "M15", "M30", "H1"]
SPREAD = 0.20
BALANCE = 100.0
LOT = BALANCE / 10000.0

end_bkk = datetime.now(BKK)
results = {}

t0 = time.time()
for strat in STRATS:
    mod = importlib.import_module(f"{strat}.backtest_{strat}")
    results[strat] = {tf: {} for tf in TF_LIST}
    for tf in TF_LIST:
        for d in WINDOWS_DAYS:
            start_bkk = end_bkk - timedelta(days=d)
            try:
                summary, _trades = mod.backtest(tf, SPREAD, LOT, start_bkk, end_bkk)
                results[strat][tf][d] = summary.get("net_profit")
            except RuntimeError:
                results[strat][tf][d] = None
            except Exception as exc:  # noqa: BLE001
                print(f"[ERROR] {strat} {tf} {d}d: {exc}", file=sys.stderr, flush=True)
                results[strat][tf][d] = None
            elapsed = time.time() - t0
            print(f"[{elapsed:7.1f}s] {strat} {tf} {d}d -> {results[strat][tf][d]}", flush=True)

print("\n\n===== JSON RESULT =====")
print(json.dumps(results, indent=2))

print("\n\n===== TF ที่กำไรตลอด (ทุกหน้าต่างที่มีข้อมูล) =====")
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
