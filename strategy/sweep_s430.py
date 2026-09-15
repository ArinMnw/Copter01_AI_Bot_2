# -*- coding: utf-8 -*-
"""ไล่ backtest S430 ทุก TF (M1/M15/M30/H1/H4/H12/D1) x หน้าต่างเวลาหลายขนาด
(30/60/90/120/150/180/270/365 วันย้อนหลังจากตอนนี้) — ใช้ default cfg ของ
strategy430 (ไม่ tune) fixed lot (balance=100 -> lot=0.01) spread=0.20

Usage: python sweep_s430.py > sweep_result_s430.txt
"""

from __future__ import annotations

import importlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone

BKK = timezone(timedelta(hours=7))
WINDOWS_DAYS = [30, 60, 90, 120, 150, 180, 270, 365]
TF_LIST = ["M1", "M15", "M30", "H1", "H4", "H12", "D1"]
SPREAD = 0.20
BALANCE = 100.0
LOT = BALANCE / 10000.0

end_bkk = datetime.now(BKK)

mod = importlib.import_module("s430.backtest_s430")
results = {tf: {} for tf in TF_LIST}

t0 = time.time()
for tf in TF_LIST:
    for d in WINDOWS_DAYS:
        start_bkk = end_bkk - timedelta(days=d)
        try:
            summary, _trades = mod.backtest(tf, SPREAD, LOT, start_bkk, end_bkk)
            results[tf][d] = summary
        except RuntimeError as exc:
            results[tf][d] = {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001 - ไม่อยากให้ 1 error ล้มทั้ง sweep
            print(f"[ERROR] {tf} {d}d: {exc}", file=sys.stderr, flush=True)
            results[tf][d] = {"error": str(exc)}
        elapsed = time.time() - t0
        net = results[tf][d].get("net_profit") if isinstance(results[tf][d], dict) else None
        print(f"[{elapsed:7.1f}s] s430 {tf} {d}d -> {net}", flush=True)

print("\n\n===== JSON RESULT =====")
print(json.dumps(results, indent=2, default=str))
