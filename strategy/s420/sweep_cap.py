# -*- coding: utf-8 -*-
"""สวีป max_concurrent (cap) หลายค่า x ทุก TF ของ S420 เพื่อดู P&L vs MaxDD
trade-off ก่อนตัดสินใจว่าจะปรับ cap เท่าไหร่ (ปัจจุบัน live cap=1)

Usage: python sweep_cap.py > sweep_cap_result.txt
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")
from backtest_s420 import backtest, TF_MAP, BKK

CAPS = [1, 2, 3, 5]
TF_LIST = list(TF_MAP)
DAYS = 30
SPREAD = 0.20
BALANCE = 10000.0
LOT = BALANCE / 10000.0


def main():
    # ⚠️ ต้องอยู่ใต้ if __name__ == "__main__" เท่านั้น — backtest() เรียก
    # multiprocessing.Pool ภายใน (ผ่าน compute_signals_parallel) บน Windows ใช้
    # spawn start method ซึ่ง import สคริปต์นี้ซ้ำใน child process ถ้าโค้ดสร้าง
    # Pool อยู่นอก guard นี้ child จะพยายามสร้าง Pool ซ้อนอีกชั้นจนพัง (เจอจริง:
    # รันรอบแรกได้ error "attempt has been made to start a new process before
    # the current process has finished its bootstrapping phase" เกือบทุก
    # TF/cap ยกเว้นตัวเดียวที่รอดมาได้)
    end_bkk = datetime.now(BKK)
    start_bkk = end_bkk - timedelta(days=DAYS)

    results = {}
    t0 = time.time()
    for tf in TF_LIST:
        results[tf] = {}
        for cap in CAPS:
            try:
                summary, trades = backtest(tf, SPREAD, LOT, start_bkk, end_bkk, max_concurrent=cap)
                results[tf][cap] = summary
            except RuntimeError as exc:
                results[tf][cap] = {"error": str(exc)}
            except Exception as exc:  # noqa: BLE001
                print(f"[ERROR] {tf} cap={cap}: {exc}", file=sys.stderr, flush=True)
                results[tf][cap] = {"error": str(exc)}
            elapsed = time.time() - t0
            r = results[tf][cap]
            net = r.get("net_profit") if isinstance(r, dict) else None
            dd = r.get("max_drawdown") if isinstance(r, dict) else None
            closed = r.get("closed") if isinstance(r, dict) else None
            print(f"[{elapsed:7.1f}s] {tf} cap={cap} -> net={net} dd={dd} closed={closed}", flush=True)

    print("\n\n===== JSON RESULT =====")
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
