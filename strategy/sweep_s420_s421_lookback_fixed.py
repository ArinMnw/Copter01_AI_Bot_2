# -*- coding: utf-8 -*-
"""สวีป S420/S421 หลังแก้บั๊ก LOOKBACK_BARS (per-TF ตรงกับ live) — จำกัดแค่
30/60 วัน ตามที่พี่ขอ (270/365 วันบน M1 ช้าเกินไปหลัง lookback ขยับจาก 1200
เป็น 18000 แท่ง)"""

from __future__ import annotations

import importlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone

BKK = timezone(timedelta(hours=7))
STRATS = ["s420", "s421"]
WINDOWS_DAYS = [30, 60]
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
                results[strat][tf][d] = summary
            except RuntimeError as exc:
                results[strat][tf][d] = None
                print(f"[SKIP] {strat} {tf} {d}d: {exc}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[ERROR] {strat} {tf} {d}d: {exc}", file=sys.stderr, flush=True)
                results[strat][tf][d] = None
            elapsed = time.time() - t0
            summ = results[strat][tf][d]
            np_ = summ.get("net_profit") if summ else None
            pf = summ.get("profit_factor") if summ else None
            print(f"[{elapsed:7.1f}s] {strat} {tf} {d}d -> net={np_} pf={pf}", flush=True)

print("\n\n===== JSON RESULT =====")
print(json.dumps(results, indent=2, default=str))

print("\n\n===== ตาราง P&L/PF ต่อ TF/หน้าต่าง =====")
for strat in STRATS:
    print(f"\n=== {strat.upper()} ===")
    header = "TF   " + "".join(f"{('%dd net'%w):>14}{('%dd PF'%w):>10}" for w in WINDOWS_DAYS)
    print(header)
    for tf in TF_LIST:
        row = f"{tf:<5}"
        for w in WINDOWS_DAYS:
            summ = results[strat][tf].get(w)
            if summ is None:
                row += f"{'N/A':>14}{'':>10}"
            else:
                row += f"{summ['net_profit']:>14.2f}"
                pf = summ.get("profit_factor")
                if pf is None:
                    row += f"{'N/A':>10}"
                elif pf == float("inf"):
                    row += f"{'inf':>10}"
                else:
                    row += f"{pf:>10.2f}"
        print(row)
