# -*- coding: utf-8 -*-
"""run_s20_300_v2_walk_forward.py
Walk-forward validation สำหรับ S20.300 v2:
  1. Single split IS 70% / OOS 30% ตามเวลา (กฎข้อ 15) ไม่จูนพารามิเตอร์ระหว่างสองช่วง
  2. Rolling walk-forward N ช่วงต่อเนื่องเท่าๆกัน (ตั้ง --folds ปรับได้ default 6)
ผลที่ผ่านแล้ว (365 วัน, พารามิเตอร์ default): IS PF 1.78 / OOS PF 1.65 (14/14 เดือนบวก),
rolling 6 ช่วง 6/6 บวก PF 1.54-2.14 — ดู strategy/backtest-summary/s20_300_v2_walk_forward.md
และ s20_300_v2_rolling_walk_forward.md
"""
import os, sys, json, argparse
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5

sys.path.insert(0, os.path.dirname(__file__))
from v2_zone_ltf_trigger import init_mt5, fetch_data, build_merged_zones, generate_setups, run_backtest, DEFAULT_CFG  # noqa: E402


def summarize(res):
    return {"trades": res["trades"], "wr": res["wr"], "net": res["pnl"], "pf": res["pf"], "dd": res["max_dd"],
            "monthly": {m: {"trades": v["trades"], "pnl": round(v["pnl"], 2)} for m, v in res["monthly_stats"].items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=6, help="จำนวนช่วง rolling walk-forward")
    ap.add_argument("--out", default=None, help="path ไฟล์ JSON ผลลัพธ์ (default: เครื่องปัจจุบัน)")
    args = ap.parse_args()

    if not init_mt5():
        print("MT5 Init Failed")
        return
    symbol = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)
    rates_zone, m5 = fetch_data(symbol, start_dt, now)
    mt5.shutdown()
    _, merged_per_tf = build_merged_zones(rates_zone, m5)
    setups = generate_setups(merged_per_tf)
    print("total setups (dedup):", len(setups), flush=True)

    # 1) single split 70/30
    t_min, t_max = setups[0]["time"], setups[-1]["time"]
    cutoff = t_min + int((t_max - t_min) * 0.70)
    is_setups = [s for s in setups if s["time"] < cutoff]
    oos_setups = [s for s in setups if s["time"] >= cutoff]
    res_is = run_backtest(m5, is_setups)
    res_oos = run_backtest(m5, oos_setups)
    print(f"IS  (70%, ก่อน {datetime.fromtimestamp(cutoff, tz=timezone.utc)}): "
          f"trades={res_is['trades']} pf={res_is['pf']:.2f} net={res_is['pnl']:.2f}", flush=True)
    print(f"OOS (30%, หลัง {datetime.fromtimestamp(cutoff, tz=timezone.utc)}): "
          f"trades={res_oos['trades']} pf={res_oos['pf']:.2f} net={res_oos['pnl']:.2f}", flush=True)

    # 2) rolling N ช่วง
    n = args.folds
    span = t_max - t_min
    bounds = [t_min + int(span * i / n) for i in range(n + 1)]
    folds = []
    for i in range(n):
        lo, hi = bounds[i], bounds[i + 1]
        fold_setups = [s for s in setups if lo <= s["time"] < (hi if i < n - 1 else hi + 1)]
        res = run_backtest(m5, fold_setups)
        folds.append({"fold": i + 1, "start_utc": str(datetime.fromtimestamp(lo, tz=timezone.utc)),
                      "end_utc": str(datetime.fromtimestamp(hi, tz=timezone.utc)), **summarize(res)})
        print(f"fold {i+1}: trades={folds[-1]['trades']} pf={folds[-1]['pf']:.2f} net={folds[-1]['net']:.2f}", flush=True)

    out = {"in_sample_70pct": summarize(res_is), "out_of_sample_30pct": summarize(res_oos),
           "is_cutoff_utc": str(datetime.fromtimestamp(cutoff, tz=timezone.utc)),
           "rolling_folds": folds}
    out_path = args.out or os.path.join(os.path.dirname(__file__), "S20_300_v2_walk_forward_result.json")
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=1, default=str)
    print("saved:", out_path, flush=True)


if __name__ == "__main__":
    main()
