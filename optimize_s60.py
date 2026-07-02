"""
optimize_s60.py — grid search สำหรับ S60 Asian Range Sweep Reversal
"""

import csv
import itertools
import os
import argparse
from datetime import datetime

import MetaTrader5 as mt5

import config
from strategy60 import S60_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s60_backtest as s60sim


def score_fixed(raw, days, spread):
    return s60sim._fixed_lot_stats(raw, days, spread)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--spread", type=float, default=0.20)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    days = args.days
    spread = args.spread
    if not config.mt5_initialize(mt5):
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return
    entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=420)
    htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=140)
    mt5.shutdown()

    if args.quick:
        sweeps = [0.10, 0.25, 0.40]
        rejects = [0.05, 0.15]
        minranges = [1.0, 2.5]
        bodies = [0.0, 0.15]
        sls = [0.6, 1.0]
        rrs = [0.8, 1.2, 1.6]
        modes = ["reversal", "breakout"]
        conftypes = ["none"]
    else:
        sweeps = [0.10, 0.20, 0.35]
        rejects = [0.05, 0.10, 0.20]
        minranges = [1.0, 2.0, 3.0]
        bodies = [0.0, 0.10, 0.20]
        sls = [0.5, 0.8, 1.0]
        rrs = [0.8, 1.0, 1.2, 1.5]
        modes = ["reversal", "breakout"]
        conftypes = ["none", "htf_trend"]

    rows = []
    total = 0
    for mode, sweep, reject, minrange, body, sl, rr, conf in itertools.product(
            modes, sweeps, rejects, minranges, bodies, sls, rrs, conftypes):
        total += 1
        cfg = dict(S60_DEFAULTS)
        cfg.update(MODE=mode, SWEEP_ATR_MULT=sweep, REJECT_ATR_MULT=reject, MIN_RANGE_ATR=minrange,
                   BODY_ATR_MULT=body, SL_ATR_MULT=sl, TP_RR=rr, CONFIRMATION_TYPE=conf)
        raw = s60sim.run_single(entry_bars, htf_bars, cfg, days, spread)
        fs = score_fixed(raw, days, spread)
        rows.append({
            "label": f"{mode}_sw{sweep}_rej{reject}_mr{minrange}_body{body}_sl{sl}_rr{rr}_{conf}",
            "mode": mode, "sweep": sweep, "reject": reject, "minrange": minrange, "body": body,
            "sl": sl, "rr": rr, "conf": conf, **fs,
        })
        if total % 10 == 0:
            best = max(rows, key=lambda r: (r["fixed_pf"], r["sharpe_like"], r["fixed_per_day"]))
            print(f"{total} combos | best PF={best['fixed_pf']:.2f} $/d={best['fixed_per_day']:.2f} "
                  f"sharpe={best['sharpe_like']:.3f} {best['label']}")

    rows.sort(key=lambda r: (r["fixed_pf"], r["sharpe_like"], r["fixed_per_day"]), reverse=True)
    out = "s60_backtest_summary.csv"
    fields = ["timestamp", "label", "mode", "sweep", "reject", "minrange", "body", "sl", "rr", "conf",
              "trades", "wr", "fixed_pnl", "fixed_per_day", "fixed_per_month", "fixed_pf",
              "fixed_avg", "pct_pos_days", "max_losing_day_streak", "sharpe_like"]
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
