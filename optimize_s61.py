"""
optimize_s61.py — grid search สำหรับ S61 CYQONX Three-Line
"""

import argparse
import csv
import itertools
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
from strategy61 import S61_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s61_backtest as s61sim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    spread = 0.20

    if not config.mt5_initialize(mt5):
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return
    entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", args.days, extra_bars=360)
    mt5.shutdown()

    if args.quick:
        mean_periods = [24, 48, 96]
        dev_types = ["atr", "std"]
        dev_periods = [24, 48]
        entry_zs = [0.8, 1.0, 1.25]
        phases = [3, 4]
        slope_filters = ["none", "mean_flat"]
        sls = [0.8, 1.2]
        tp_modes = ["mean", "rr"]
        rrs = [0.8, 1.2]
    else:
        mean_periods = [24, 36, 48, 72, 96]
        dev_types = ["atr", "std"]
        dev_periods = [24, 48, 72]
        entry_zs = [0.7, 0.9, 1.1, 1.4]
        phases = [3, 4, 5]
        slope_filters = ["none", "mean_flat", "counter_slope"]
        sls = [0.6, 0.9, 1.2]
        tp_modes = ["mean", "rr"]
        rrs = [0.8, 1.0, 1.3]

    rows = []
    total = 0
    for mp, dt, dp, ez, ph, sf, sl, tm, rr in itertools.product(
            mean_periods, dev_types, dev_periods, entry_zs, phases, slope_filters, sls, tp_modes, rrs):
        total += 1
        cfg = dict(S61_DEFAULTS)
        cfg.update(MEAN_PERIOD=mp, DEV_TYPE=dt, DEV_PERIOD=dp, ENTRY_Z=ez,
                   PHASE_LOOKBACK=ph, SLOPE_FILTER=sf, SL_ATR_MULT=sl,
                   TP_MODE=tm, TP_RR=rr)
        raw = s61sim.run_single(entry_bars, None, cfg, args.days, spread)
        fs = s61sim._fixed_lot_stats(raw, args.days, spread)
        label = f"mp{mp}_{dt}{dp}_z{ez}_ph{ph}_{sf}_sl{sl}_{tm}_rr{rr}"
        rows.append({"label": label, "mean_period": mp, "dev_type": dt, "dev_period": dp,
                     "entry_z": ez, "phase": ph, "slope_filter": sf, "sl": sl,
                     "tp_mode": tm, "rr": rr, **fs})
        if total % 50 == 0:
            best = max(rows, key=lambda r: (r["fixed_pf"], r["sharpe_like"], r["fixed_per_day"]))
            print(f"{total} combos | best PF={best['fixed_pf']:.2f} $/d={best['fixed_per_day']:.2f} "
                  f"sharpe={best['sharpe_like']:.3f} n={best['trades']} {best['label']}")

    rows.sort(key=lambda r: (r["fixed_pf"], r["sharpe_like"], r["fixed_per_day"]), reverse=True)
    out = "s61_backtest_summary.csv"
    fields = ["timestamp", "label", "mean_period", "dev_type", "dev_period", "entry_z", "phase",
              "slope_filter", "sl", "tp_mode", "rr", "trades", "wr", "fixed_pnl",
              "fixed_per_day", "fixed_per_month", "fixed_pf", "fixed_avg", "pct_pos_days",
              "max_losing_day_streak", "sharpe_like"]
    is_new = not os.path.exists(out)
    with open(out, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for r in rows:
            w.writerow({"timestamp": ts, **{k: r.get(k) for k in fields if k != "timestamp"}})
    print("\nTop 15 fixed-lot candidates:")
    for i, r in enumerate(rows[:15], 1):
        print(f"{i:>2}. PF={r['fixed_pf']:.3f} $/d={r['fixed_per_day']:>7.2f} "
              f"sharpe={r['sharpe_like']:.3f} n={r['trades']:>4} streak={r['max_losing_day_streak']} "
              f"{r['label']}")
    print(f"\n-> {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
