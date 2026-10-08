# -*- coding: utf-8 -*-
"""run_group1_v2_sweep_prototype.py
⚠️ ยังไม่ validate — ทดลองดีไซน์ v2 (strategy/s20.300/v2_zone_ltf_trigger.py) กับกลยุทธ์กลุ่ม 1
ทั้ง 34 ตัว (S20.31-53, 130-139, 300) มีแค่ S20.300 ตัวเดียวที่ผ่าน walk-forward/sensitivity ครบ
(ดู strategy/s20.300/run_s20_300_v2_*.py) ส่วนอีก 33 ตัวในสคริปต์นี้คือ aggregate เดียว ยังไม่ผ่าน
walk-forward และพารามิเตอร์ของ S20.31-36 เป็นค่าประมาณ (ไม่ใช่ค่าจริงจาก module ของตัวเอง)

ผลล่าสุด (2026-10-03, 365 วัน): PF เฉลี่ย 1.45, 31/34 ตัวเป็นบวก — รายละเอียดดู
strategy/backtest-summary/group1_design_v2_zone_ltf_trigger_all34.md

ใช้ค่า env ONLY_SID=<เลข sid> รันตัวเดียว (ต่อจากผลเดิมถ้าไฟล์ output มีอยู่แล้ว)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "s20.300"))
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
from run_master_s20_marathon_201_to_300 import make_stages
from v2_zone_ltf_trigger import init_mt5, fetch_data, build_merged_zones, generate_setups, run_backtest, ZONE_TFS

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "group1_v2_sweep_result.json")

# sid -> cfg (tfs, min_vol, min_wick, retest_depth, sl_mult, tp_r, stages)
SIDS = {}


def reg(sid, tfs, min_vol, min_wick, retest_depth, sl_mult, tp_r, stages):
    SIDS[sid] = dict(tfs=tfs, min_vol=min_vol, min_wick=min_wick, retest_depth=retest_depth, sl_mult=sl_mult, tp_r=tp_r, stages=stages)


# 31-36: ไม่มีค่าเปิดเผยผ่าน s20_institutional_hub.py (module ภายในมีค่าของตัวเอง) ใช้ค่ากลางเทียบ
for sid, tf_tuple, tp_r in [
    (31, ("M30",), 1.8), (32, ("M30", "M15"), 2.5), (33, ("H1", "M30", "M15"), 2.8),
    (34, ("H1", "M30", "M15"), 2.6), (35, ("H4", "H1", "M30", "M15"), 2.8), (36, ("H4", "H1", "M30", "M15"), 3.5),
]:
    n = max(2, round(tp_r / 0.5))
    reg(sid, tf_tuple, 1.2, 0.30, 0.13, 0.2, tp_r, make_stages(n))

reg(40, ("H4", "H2", "H1", "M30", "M15"), 1.20, 0.30, 0.130, 0.2, 5.0, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3)])
reg(37, ("H4", "H1", "M30", "M15"), 1.2, 0.30, 0.15, 0.2, 4.0, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3)])
reg(38, ("H4", "H1", "M30", "M15"), 1.2, 0.30, 0.13, 0.2, 4.2, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5)])
reg(39, ("H4", "H1", "M30", "M15"), 1.2, 0.30, 0.13, 0.2, 4.6, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9)])
reg(41, ("H4", "H3", "H2", "H1", "M30", "M15"), 1.2, 0.30, 0.13, 0.2, 5.0, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3)])
reg(42, ("H4", "H3", "H2", "H1", "M30", "M20", "M15"), 1.2, 0.30, 0.128, 0.2, 5.6, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9)])
reg(43, ZONE_TFS, 1.2, 0.30, 0.122, 0.2, 5.8, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2)])
reg(44, ZONE_TFS, 1.2, 0.30, 0.121, 0.2, 5.8, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2)])
reg(45, ZONE_TFS, 1.2, 0.30, 0.121, 0.2, 5.85, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.3)])
reg(46, ZONE_TFS, 1.18, 0.36, 0.121, 0.2, 5.9, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4)])
reg(47, ZONE_TFS, 1.17, 0.34, 0.122, 0.2, 6.05, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6)])
reg(48, ZONE_TFS, 1.17, 0.34, 0.122, 0.2, 6.35, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8)])
reg(49, ZONE_TFS, 1.17, 0.34, 0.122, 0.2, 6.7, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95)])
reg(50, ZONE_TFS, 1.17, 0.33, 0.124, 0.2, 6.65, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15)])
reg(51, ZONE_TFS, 1.17, 0.32, 0.124, 0.2, 6.75, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3)])
reg(52, ZONE_TFS, 1.17, 0.30, 0.124, 0.2, 6.9, [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5)])
reg(53, ZONE_TFS, 1.17, 0.295, 0.124, 0.195, 6.98, make_stages(17))
reg(130, ZONE_TFS, 1.17, 0.14, 0.125, 0.195, 11.36, make_stages(35))
for sid, tp_r, n in [(131, 11.40, 35), (132, 11.38, 35), (133, 11.45, 37), (134, 11.55, 38), (135, 11.60, 38),
                     (136, 11.90, 42), (137, 11.95, 43), (138, 12.15, 46), (139, 12.50, 50)]:
    reg(sid, ZONE_TFS, 1.17, 0.14, 0.125, 0.195, tp_r, make_stages(n))
reg(300, ZONE_TFS, 1.17, 0.14, 0.125, 0.195, 13.43, make_stages(55))


def main():
    if not init_mt5():
        print("MT5 init failed")
        return
    sym = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)
    rates_zone, m5 = fetch_data(sym, start_dt, now)
    mt5.shutdown()
    _, merged_per_tf = build_merged_zones(rates_zone, m5)

    results = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    only = os.environ.get("ONLY_SID")
    items = [(int(only), SIDS[int(only)])] if only else list(SIDS.items())
    for sid, cfg in items:
        setups = generate_setups(merged_per_tf, cfg, zone_tfs=cfg["tfs"])
        res = run_backtest(m5, setups, cfg)
        results[f"S20.{sid}"] = {"trades": res["trades"], "wr": res["wr"], "net": res["pnl"], "pf": res["pf"], "dd": res["max_dd"]}
        print(f"S20.{sid}", results[f"S20.{sid}"], flush=True)
        json.dump(results, open(OUT, "w", encoding="utf-8"), indent=1)
    print("ALL DONE", len(results))


if __name__ == "__main__":
    main()
