# -*- coding: utf-8 -*-
import json, sys, time
from datetime import datetime, timedelta
sys.path.insert(0, ".")
from backtest_s420 import backtest, TF_MAP, BKK

TF_LIST = list(TF_MAP)
DAYS = 30
SPREAD = 0.20
LOT = 10000.0 / 10000.0

def main():
    end_bkk = datetime.now(BKK)
    start_bkk = end_bkk - timedelta(days=DAYS)
    results = {}
    t0 = time.time()
    for tf in TF_LIST:
        try:
            summary, trades = backtest(tf, SPREAD, LOT, start_bkk, end_bkk, max_concurrent=999)
            results[tf] = summary
        except Exception as exc:
            results[tf] = {"error": str(exc)}
        elapsed = time.time() - t0
        r = results[tf]
        print(f"[{elapsed:7.1f}s] {tf} cap=999 -> net={r.get('net_profit')} dd={r.get('max_drawdown')} closed={r.get('closed')}", flush=True)
    print("\n\n===== JSON RESULT =====")
    print(json.dumps(results, indent=2, default=str))

if __name__ == "__main__":
    main()
