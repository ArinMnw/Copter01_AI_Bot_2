# -*- coding: utf-8 -*-
"""run_s20_300_v2_sensitivity.py
Rule #14 sensitivity test: ขยับ min_vol/min_wick/sl_mult/retest_depth ทีละตัว (ตัวอื่นคงที่ที่ base)
ดูว่า PF มั่นคงไหม ไม่ใช่การจูนหาค่าที่ดีกว่า base (Rule #14 ห้ามจูนชนะทีละนิดแล้วถือว่าดีขึ้น)
ผลที่ผ่านแล้ว: PF 1.55-1.90 ทุกค่า ไม่มี knife-edge — ดู
strategy/backtest-summary/s20_300_v2_sensitivity_test.md
"""
import os, sys, json
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5

sys.path.insert(0, os.path.dirname(__file__))
from v2_zone_ltf_trigger import init_mt5, fetch_data, build_merged_zones, generate_setups, run_backtest, DEFAULT_CFG  # noqa: E402

SWEEP = {
    "min_vol": [1.05, 1.11, 1.17, 1.25, 1.35],
    "min_wick": [0.10, 0.12, 0.14, 0.18, 0.22],
    "sl_mult": [0.15, 0.175, 0.195, 0.22, 0.25],
    "retest_depth": [0.08, 0.10, 0.125, 0.15, 0.18],
}


def main():
    if not init_mt5():
        print("MT5 Init Failed")
        return
    symbol = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)
    rates_zone, m5 = fetch_data(symbol, start_dt, now)
    mt5.shutdown()
    _, merged_per_tf = build_merged_zones(rates_zone, m5)

    results = {}

    def run_cfg(label, cfg):
        setups = generate_setups(merged_per_tf, cfg)
        res = run_backtest(m5, setups, cfg)
        row = {"trades": res["trades"], "wr": res["wr"], "net": res["pnl"], "pf": res["pf"], "dd": res["max_dd"]}
        results[label] = row
        print(label, row, flush=True)

    run_cfg("base", DEFAULT_CFG)
    for param, values in SWEEP.items():
        for v in values:
            if abs(v - DEFAULT_CFG[param]) < 1e-9:
                continue
            cfg = dict(DEFAULT_CFG)
            cfg[param] = v
            run_cfg(f"{param}={v}", cfg)

    out_path = os.path.join(os.path.dirname(__file__), "S20_300_v2_sensitivity_result.json")
    json.dump(results, open(out_path, "w", encoding="utf-8"), indent=1)
    print("saved:", out_path, flush=True)


if __name__ == "__main__":
    main()
